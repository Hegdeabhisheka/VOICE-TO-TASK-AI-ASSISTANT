"""SQLite persistence layer (stdlib only)."""
from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
from typing import Any, Iterator

from core import config

_UPDATABLE = ("title", "deadline", "priority", "category", "status", "notes", "source")
_STOPWORDS = frozenset({
    "the", "a", "an", "my", "to", "of", "for", "task", "tasks", "reminder", "please",
    "and", "on", "in", "at", "called", "named", "that", "this", "it", "with",
})

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT NOT NULL,
    deadline     TEXT,
    priority     TEXT NOT NULL DEFAULT 'medium',
    category     TEXT NOT NULL DEFAULT 'other',
    notes        TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL DEFAULT 'pending',
    source       TEXT NOT NULL DEFAULT 'voice',
    created_at   TEXT NOT NULL,
    completed_at TEXT
);
CREATE TABLE IF NOT EXISTS interactions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_text   TEXT NOT NULL,
    intent     TEXT NOT NULL,
    confidence REAL NOT NULL,
    success    INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_deadline ON tasks(deadline);
"""


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    """Open a short-lived connection, commit on success, roll back on error, always close."""
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(config.DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _naive(dt: datetime | None) -> datetime | None:
    """Convert aware datetimes to naive local time."""
    if dt is not None and dt.tzinfo is not None:
        return dt.astimezone().replace(tzinfo=None)
    return dt


def _to_iso(dt: datetime | None) -> str | None:
    dt = _naive(dt)
    return dt.isoformat(timespec="seconds") if dt else None


def _from_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _row_to_task(row: sqlite3.Row) -> dict:
    """Convert a DB row to a task dict with parsed datetimes and an `overdue` flag."""
    task = dict(row)
    for key in ("deadline", "created_at", "completed_at"):
        task[key] = _from_iso(task.get(key))
    deadline = task["deadline"]
    task["overdue"] = bool(
        task["status"] == "pending" and deadline is not None and deadline < datetime.now()
    )
    return task


def init_db() -> None:
    """Create tables if they do not exist."""
    with _connect() as conn:
        conn.executescript(_SCHEMA)


def add_task(title: str, deadline: datetime | None, priority: str, category: str,
             notes: str = "", source: str = "voice") -> int:
    """Insert a task and return its id. Invalid priority/category fall back to defaults."""
    title = (title or "").strip()
    if not title:
        raise ValueError("A task needs a title.")
    priority = (priority or "").lower()
    if priority not in config.PRIORITIES:
        priority = config.DEFAULT_PRIORITY
    category = (category or "").lower()
    if category not in config.CATEGORIES:
        category = config.DEFAULT_CATEGORY
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO tasks (title, deadline, priority, category, notes, status, source, created_at) "
            "VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)",
            (title, _to_iso(deadline), priority, category, notes or "", source,
             _to_iso(datetime.now())),
        )
        return int(cur.lastrowid)


def _sort_pending(task: dict) -> tuple:
    deadline = task["deadline"]
    rank = config.PRIORITIES.index(task["priority"]) if task["priority"] in config.PRIORITIES else 0
    return (deadline is None, deadline or datetime.max, -rank)


def list_tasks(status: str | None = None) -> list[dict]:
    """List tasks. Pending first (by deadline, then priority), then done (newest completion first)."""
    query, params = "SELECT * FROM tasks", ()
    if status in ("pending", "done"):
        query += " WHERE status = ?"
        params = (status,)
    with _connect() as conn:
        tasks = [_row_to_task(r) for r in conn.execute(query, params).fetchall()]
    pending = sorted((t for t in tasks if t["status"] == "pending"), key=_sort_pending)
    done = sorted((t for t in tasks if t["status"] == "done"),
                  key=lambda t: t["completed_at"] or datetime.min, reverse=True)
    return pending + done


def get_task(task_id: int) -> dict | None:
    """Fetch one task by id."""
    with _connect() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return _row_to_task(row) if row else None


def update_task(task_id: int, **fields: Any) -> bool:
    """Update whitelisted fields. Returns True if a row changed."""
    updates: dict[str, Any] = {}
    for key, value in fields.items():
        if key not in _UPDATABLE:
            continue
        if key == "deadline":
            value = _to_iso(value)
        elif key == "priority":
            value = str(value).lower()
            if value not in config.PRIORITIES:
                return False
        elif key == "category":
            value = str(value).lower()
            if value not in config.CATEGORIES:
                value = config.DEFAULT_CATEGORY
        elif key == "status":
            if value not in ("pending", "done"):
                return False
        elif key == "title":
            value = str(value).strip()
            if not value:
                return False
        updates[key] = value
    if not updates:
        return False
    if "status" in updates:
        updates["completed_at"] = _to_iso(datetime.now()) if updates["status"] == "done" else None
    assignments = ", ".join(f"{key} = ?" for key in updates)  # keys are whitelisted above
    with _connect() as conn:
        cur = conn.execute(f"UPDATE tasks SET {assignments} WHERE id = ?",
                           [*updates.values(), task_id])
        return cur.rowcount > 0


def complete_task(task_id: int) -> bool:
    """Mark a task as done."""
    return update_task(task_id, status="done")


def delete_task(task_id: int) -> bool:
    """Delete a task."""
    with _connect() as conn:
        return conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,)).rowcount > 0


def _stem(word: str) -> str:
    return word[:-1] if len(word) > 3 and word.endswith("s") else word


def _tokens(text: str) -> list[str]:
    return [_stem(w) for w in re.findall(r"[a-z0-9']+", text.lower()) if w not in _STOPWORDS]


def _similarity(query: str, title: str) -> float:
    """Fuzzy similarity in [0, 1], tolerant to ASR typos and word-order changes."""
    q, t = query.lower().strip(), title.lower().strip()
    if not q or not t:
        return 0.0
    if q == t:
        return 1.0
    ratio = SequenceMatcher(None, q, t).ratio()
    q_tokens, t_tokens = _tokens(q), _tokens(t)
    if not q_tokens or not t_tokens:
        return ratio
    token_fuzzy = sum(
        max(SequenceMatcher(None, qt, tt).ratio() for tt in t_tokens) for qt in q_tokens
    ) / len(q_tokens)
    overlap = len(set(q_tokens) & set(t_tokens)) / len(set(q_tokens))
    substring = 0.92 if (q in t or t in q) else 0.0
    return max(ratio, overlap * 0.95, token_fuzzy * 0.9, substring)


def find_tasks(query: str, status: str | None = "pending") -> list[dict]:
    """Fuzzy title search; results carry a `match_score` and are sorted best-first."""
    if not (query or "").strip():
        return []
    results = []
    for task in list_tasks(status):
        score = _similarity(query, task["title"])
        if score >= config.FUZZY_MATCH_THRESHOLD:
            results.append({**task, "match_score": round(score, 3)})
    results.sort(key=lambda t: t["match_score"], reverse=True)
    return results


def log_interaction(raw_text: str, intent: str, confidence: float, success: bool) -> None:
    """Record one voice/text interaction for scoring."""
    confidence = max(0.0, min(1.0, float(confidence or 0.0)))
    with _connect() as conn:
        conn.execute(
            "INSERT INTO interactions (raw_text, intent, confidence, success, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (raw_text or "", intent or "unknown", confidence, int(bool(success)),
             _to_iso(datetime.now())),
        )


def _streak(days: set[str], today: date) -> int:
    """Consecutive days (ending today or yesterday) with at least one completed task."""
    cursor = today if today.isoformat() in days else today - timedelta(days=1)
    count = 0
    while cursor.isoformat() in days:
        count += 1
        cursor -= timedelta(days=1)
    return count


def get_stats() -> dict:
    """Aggregate statistics used by the scoring engine and the UI."""
    now = datetime.now()
    now_iso, today = _to_iso(now), now.date()
    with _connect() as conn:
        def scalar(sql: str, params: tuple = ()) -> int:
            return int(conn.execute(sql, params).fetchone()[0])

        total = scalar("SELECT COUNT(*) FROM tasks")
        done = scalar("SELECT COUNT(*) FROM tasks WHERE status = 'done'")
        pending = scalar("SELECT COUNT(*) FROM tasks WHERE status = 'pending'")
        overdue = scalar("SELECT COUNT(*) FROM tasks WHERE status = 'pending' "
                         "AND deadline IS NOT NULL AND deadline < ?", (now_iso,))
        due_today = scalar("SELECT COUNT(*) FROM tasks WHERE status = 'pending' "
                           "AND deadline IS NOT NULL AND substr(deadline, 1, 10) = ?",
                           (today.isoformat(),))
        days = {r[0] for r in conn.execute(
            "SELECT DISTINCT substr(completed_at, 1, 10) FROM tasks "
            "WHERE status = 'done' AND completed_at IS NOT NULL")}
        count, avg_conf, successes = conn.execute(
            "SELECT COUNT(*), COALESCE(AVG(confidence), 0), COALESCE(SUM(success), 0) FROM interactions"
        ).fetchone()
    return {
        "total": total, "done": done, "pending": pending, "overdue": overdue,
        "due_today": due_today, "streak_days": _streak(days, today),
        "interactions": int(count), "avg_confidence": float(avg_conf),
        "success_rate": (float(successes) / count) if count else 0.0,
    }