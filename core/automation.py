"""Exports (.ics / .csv), due-soon reminders and the spoken-style daily briefing."""
from __future__ import annotations

import csv
import io
from datetime import date, datetime, timedelta, timezone

from core import config

ALARM_MINUTES: int = 15
EVENT_MINUTES: int = 30
_ICS_PRIORITY = {"urgent": 1, "high": 3, "medium": 5, "low": 9}
_RANK = {p: i for i, p in enumerate(config.PRIORITIES)}
CSV_COLUMNS = ["id", "title", "deadline", "priority", "category", "status",
               "notes", "source", "created_at", "completed_at"]


# ----------------------------------------------------------------------------- formatting
def format_day(day: date | datetime, now: datetime | None = None) -> str:
    """'Today', 'Tomorrow', 'Yesterday', a weekday ('Fri') within a week, else 'Mar 3'."""
    now = now or datetime.now()
    d = day.date() if isinstance(day, datetime) else day
    delta = (d - now.date()).days
    if delta == 0:
        return "Today"
    if delta == 1:
        return "Tomorrow"
    if delta == -1:
        return "Yesterday"
    if 2 <= delta <= 6:
        return d.strftime("%a")
    text = f"{d.strftime('%b')} {d.day}"
    return text if d.year == now.year else f"{text}, {d.year}"


def _clock(dt: datetime) -> str:
    return dt.strftime("%I:%M %p").lstrip("0")


def _spoken_clock(dt: datetime) -> str:
    hour = dt.hour % 12 or 12
    suffix = "AM" if dt.hour < 12 else "PM"
    return f"{hour} {suffix}" if dt.minute == 0 else f"{hour}:{dt.minute:02d} {suffix}"


def format_deadline(deadline: datetime | None, now: datetime | None = None) -> str:
    """Human-friendly deadline such as 'Fri 5:00 PM' or 'Tomorrow 9:00 AM'."""
    if deadline is None:
        return "no deadline"
    return f"{format_day(deadline, now)} {_clock(deadline)}"


def _join(items: list[str]) -> str:
    """'a', 'a and b', 'a, b and c'."""
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


# ----------------------------------------------------------------------------- .ics
def _esc(text: object) -> str:
    """Escape text values per RFC 5545."""
    return (str(text).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n"))


def _fold(line: str) -> list[str]:
    """Fold a content line at 75 octets (continuations start with one space), UTF-8 safe."""
    parts: list[str] = []
    current = ""
    for ch in line:
        if len((current + ch).encode("utf-8")) > 75:
            parts.append(current)
            current = " " + ch
        else:
            current += ch
    parts.append(current)
    return parts


def _utc(dt: datetime) -> datetime:
    """Naive datetimes are local time; return the UTC equivalent."""
    try:
        return dt.astimezone(timezone.utc)
    except (OverflowError, OSError, ValueError):
        return dt.replace(tzinfo=timezone.utc)


def _stamp(dt: datetime) -> str:
    return _utc(dt).strftime("%Y%m%dT%H%M%SZ")


def export_ics(tasks: list[dict]) -> bytes:
    """Export tasks that have a deadline as VEVENTs (30 min, UTC) with a 15-minute VALARM."""
    now = datetime.now(timezone.utc)
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Voice Task AI//EN",
             "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "X-WR-CALNAME:Voice Tasks"]
    for task in tasks:
        deadline = task.get("deadline")
        if not isinstance(deadline, datetime):
            continue
        title = str(task.get("title", "")).strip() or "Task"
        if task.get("status") == "done":
            title = "[Done] " + title
        description = (f"Priority: {task.get('priority', 'medium')}\n"
                       f"Category: {task.get('category', 'other')}")
        if task.get("notes"):
            description += "\n" + str(task["notes"])
        lines += [
            "BEGIN:VEVENT",
            f"UID:task-{task.get('id', 0)}@voice-task-ai",
            f"DTSTAMP:{now.strftime('%Y%m%dT%H%M%SZ')}",
            f"DTSTART:{_stamp(deadline)}",
            f"DTEND:{_stamp(deadline + timedelta(minutes=EVENT_MINUTES))}",
            f"SUMMARY:{_esc(title)}",
            f"DESCRIPTION:{_esc(description)}",
            f"CATEGORIES:{_esc(task.get('category', 'other'))}",
            f"PRIORITY:{_ICS_PRIORITY.get(task.get('priority', 'medium'), 5)}",
            "STATUS:CONFIRMED",
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            f"DESCRIPTION:{_esc('Reminder: ' + title)}",
            f"TRIGGER:-PT{ALARM_MINUTES}M",
            "END:VALARM",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    folded = [part for line in lines for part in _fold(line)]
    return ("\r\n".join(folded) + "\r\n").encode("utf-8")


# ----------------------------------------------------------------------------- .csv
def _safe_cell(value: object) -> str:
    """Format one CSV cell and neutralise spreadsheet formula injection."""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def export_csv(tasks: list[dict]) -> bytes:
    """Export tasks as UTF-8 CSV with a BOM so Excel opens it correctly."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS, lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    for task in tasks:
        writer.writerow({col: _safe_cell(task.get(col)) for col in CSV_COLUMNS})
    return buffer.getvalue().encode("utf-8-sig")


# ----------------------------------------------------------------------------- reminders
def due_soon(tasks: list[dict], minutes: int = 60) -> list[dict]:
    """Not-done tasks whose deadline falls within the next `minutes` minutes (soonest first)."""
    now = datetime.now()
    horizon = now + timedelta(minutes=minutes)
    soon = [t for t in tasks
            if t.get("status", "pending") != "done"
            and isinstance(t.get("deadline"), datetime)
            and now <= t["deadline"] <= horizon]
    return sorted(soon, key=lambda t: t["deadline"])


# ----------------------------------------------------------------------------- briefing
def _briefing(tasks: list[dict], now: datetime) -> str:
    greeting = "Good morning" if now.hour < 12 else "Good afternoon" if now.hour < 18 else "Good evening"
    pending = [t for t in tasks if t.get("status", "pending") != "done"]
    if not pending:
        return f"{greeting}! You have no pending tasks. Enjoy the free time."

    def dated(t: dict) -> bool:
        return isinstance(t.get("deadline"), datetime)

    overdue = [t for t in pending if dated(t) and t["deadline"] < now]
    today = sorted((t for t in pending if dated(t) and t["deadline"] >= now
                    and t["deadline"].date() == now.date()), key=lambda t: t["deadline"])
    top = sorted(pending, key=lambda t: (-_RANK.get(t.get("priority", "medium"), 0),
                                         t["deadline"] if dated(t) else datetime.max))[:3]

    parts = [f"{greeting}! You have {len(pending)} pending task{'s' if len(pending) != 1 else ''}."]
    if overdue:
        names = _join([str(t["title"]) for t in overdue[:3]])
        verb = "task is" if len(overdue) == 1 else "tasks are"
        parts.append(f"{len(overdue)} {verb} overdue: {names}.")
    else:
        parts.append("Nothing is overdue.")
    if today:
        names = _join([f"{t['title']} at {_spoken_clock(t['deadline'])}" for t in today[:4]])
        verb = "task is" if len(today) == 1 else "tasks are"
        parts.append(f"{len(today)} {verb} due today: {names}.")
    else:
        parts.append("Nothing else is due today.")
    names = _join([f"{t['title']} ({t.get('priority', 'medium')})" for t in top])
    parts.append(f"Your top priorit{'y is' if len(top) == 1 else 'ies are'} {names}.")
    return " ".join(parts)


def daily_briefing(tasks: list[dict]) -> str:
    """Spoken-style summary: pending count, overdue, due today and the top 3 priorities."""
    return _briefing(tasks, datetime.now())