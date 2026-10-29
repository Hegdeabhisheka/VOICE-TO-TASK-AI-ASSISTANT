"""Executes a ParsedCommand against the database and reports a Result."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from core import config, db
from core.automation import daily_briefing, format_day, format_deadline
from core.nlp import ParsedCommand

EXAMPLES = ("add buy milk tomorrow at 5pm", "mark buy milk as done",
            "reschedule the report to Friday at 3pm", "set priority of the report to high",
            "show my tasks", "give me my daily briefing")


@dataclass
class Result:
    """Outcome of executing a command."""
    ok: bool
    message: str
    task_id: int | None = None
    tasks: list[dict] = field(default_factory=list)


def _help(prefix: str) -> str:
    quoted = ", ".join(f"'{e}'" for e in EXAMPLES[:4])
    return f"{prefix} Try: {quoted} or 'show my tasks'."


def _pending_hint() -> str:
    titles = [t["title"] for t in db.list_tasks("pending")[:3]]
    if not titles:
        return "You have no pending tasks."
    return "Your pending tasks include: " + ", ".join(f"'{t}'" for t in titles) + "."


def _resolve(query: str, include_done: bool = False) -> tuple[dict | None, list[dict], str]:
    """Return (best match | None, other matches, error message)."""
    query = (query or "").strip()
    if not query:
        return None, [], "Which task do you mean? Say part of its name. " + _pending_hint()
    matches = db.find_tasks(query, status="pending")
    if not matches and include_done:
        matches = db.find_tasks(query, status=None)
    if not matches:
        return None, [], f"I couldn't find a task matching '{query}'. " + _pending_hint()
    return matches[0], matches[1:], ""


def _choice_note(others: list[dict]) -> str:
    """Tell the user which candidates were passed over."""
    if not others:
        return ""
    names = ", ".join(f"'{t['title']}'" for t in others[:2])
    return f" (Closest of {len(others) + 1} matches; also considered: {names}.)"


def _fresh(task_id: int, fallback: dict | None = None) -> list[dict]:
    task = db.get_task(task_id) or fallback
    return [task] if task else []


def _add(cmd: ParsedCommand) -> Result:
    if not cmd.title.strip():
        return Result(False, _help("I heard you want to add a task but missed what it is."))
    task_id = db.add_task(cmd.title, cmd.deadline, cmd.priority, cmd.category, source="voice")
    due = f"due {format_deadline(cmd.deadline)}" if cmd.deadline else "no deadline"
    return Result(True, f"Added '{cmd.title}' - {due}, {cmd.priority} priority", task_id, _fresh(task_id))


def _complete(cmd: ParsedCommand) -> Result:
    task, others, error = _resolve(cmd.target_query)
    if task is None:
        done = db.find_tasks(cmd.target_query, status="done") if (cmd.target_query or "").strip() else []
        if done:
            return Result(True, f"'{done[0]['title']}' is already marked as done.", done[0]["id"], [done[0]])
        return Result(False, error)
    db.complete_task(task["id"])
    return Result(True, f"Marked '{task['title']}' as done. Nice work!" + _choice_note(others),
                  task["id"], _fresh(task["id"], task))


def _delete(cmd: ParsedCommand) -> Result:
    task, others, error = _resolve(cmd.target_query, include_done=True)
    if task is None:
        return Result(False, error)
    db.delete_task(task["id"])
    return Result(True, f"Deleted '{task['title']}'." + _choice_note(others), task["id"])


def _reschedule(cmd: ParsedCommand) -> Result:
    if cmd.deadline is None:
        return Result(False, "When should I move it to? Try 'reschedule the report to Friday at 3pm'.")
    task, others, error = _resolve(cmd.target_query)
    if task is None:
        return Result(False, error)
    db.update_task(task["id"], deadline=cmd.deadline)
    return Result(True, f"Moved '{task['title']}' to {format_deadline(cmd.deadline)}." + _choice_note(others),
                  task["id"], _fresh(task["id"]))


def _set_priority(cmd: ParsedCommand) -> Result:
    if cmd.priority not in config.PRIORITIES:
        return Result(False, "Which priority should I set? Say low, medium, high or urgent.")
    task, others, error = _resolve(cmd.target_query)
    if task is None:
        return Result(False, error)
    db.update_task(task["id"], priority=cmd.priority)
    return Result(True, f"'{task['title']}' is now {cmd.priority} priority." + _choice_note(others),
                  task["id"], _fresh(task["id"]))


def _list(cmd: ParsedCommand) -> Result:
    raw = (cmd.raw_text or "").lower()
    wants_done = bool(re.search(r"\b(?:done|completed|finished)\b", raw))
    tasks = db.list_tasks("done" if wants_done else "pending")
    base = "completed" if wants_done else "pending"
    if not wants_done and re.search(r"\b(?:overdue|late|missed)\b", raw):
        tasks, base = [t for t in tasks if t.get("overdue")], "overdue"

    suffix = ""
    if cmd.deadline is not None:
        day = cmd.deadline.date()
        tasks = [t for t in tasks if isinstance(t.get("deadline"), datetime) and t["deadline"].date() == day]
        phrase = format_day(day)
        suffix = " due " + (phrase.lower() if phrase in ("Today", "Tomorrow", "Yesterday") else phrase)

    adjectives: list[str] = []
    prio = cmd.priority if cmd.priority in config.PRIORITIES else ""
    if prio and (prio != config.DEFAULT_PRIORITY or re.search(rf"\b{prio}\b", raw)):
        tasks = [t for t in tasks if t["priority"] == prio]
        adjectives.append(prio)
    if cmd.category in config.CATEGORIES and (cmd.category != "other" or "other" in raw):
        tasks = [t for t in tasks if t["category"] == cmd.category]
        adjectives.append(cmd.category)
    label = " ".join(adjectives + [base])

    if not tasks:
        return Result(True, f"You have no {label} tasks{suffix}.")
    preview = ", ".join(f"'{t['title']}'" for t in tasks[:3])
    more = f" and {len(tasks) - 3} more" if len(tasks) > 3 else ""
    plural = "s" if len(tasks) != 1 else ""
    return Result(True, f"You have {len(tasks)} {label} task{plural}{suffix}: {preview}{more}.", tasks=tasks)


def _briefing(cmd: ParsedCommand) -> Result:
    pending = db.list_tasks("pending")
    return Result(True, daily_briefing(pending), tasks=pending)


_HANDLERS: dict[str, Callable[[ParsedCommand], Result]] = {
    "add_task": _add, "complete_task": _complete, "delete_task": _delete,
    "reschedule_task": _reschedule, "set_priority": _set_priority,
    "list_tasks": _list, "daily_briefing": _briefing,
}


def _dispatch(cmd: ParsedCommand) -> Result:
    handler = _HANDLERS.get(cmd.intent)
    if handler is None:
        return Result(False, _help("I didn't catch a task command."))
    if cmd.confidence < config.MIN_COMMAND_CONFIDENCE:
        heard = (cmd.raw_text or "").strip()
        quote = f" '{heard}'" if heard else ""
        return Result(False, _help(f"I'm not sure I understood{quote} ({cmd.confidence:.0%} confident)."))
    return handler(cmd)


def execute(cmd: ParsedCommand) -> Result:
    """Run the command, always log the interaction, and never raise."""
    try:
        result = _dispatch(cmd)
    except Exception as exc:  # last-resort guard: the UI must keep working
        result = Result(False, f"Something went wrong ({type(exc).__name__}). Please try again.")
    try:
        db.log_interaction(cmd.raw_text, cmd.intent, cmd.confidence, result.ok)
    except Exception:
        pass
    return results