"""Natural-language deadline extraction ("tomorrow at 5pm", "next Friday", "in 2 hours")."""
from __future__ import annotations

import calendar
import re
from datetime import date, datetime, time, timedelta

from core import config

try:  # dateparser resolves calendar dates ("March 3", "4/20"); a manual fallback exists
    import dateparser
except Exception:  # pragma: no cover
    dateparser = None

WEEKDAYS = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6}
MONTHS = {"january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
          "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
          "december": 12, "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7,
          "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12}
_NUMBER_WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                 "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "fifteen": 15,
                 "twenty": 20, "thirty": 30}

_PFX = r"(?:\b(?:by|on|before|until|till|due|for)\s+)?"
_MONTH_ALT = "|".join(sorted(MONTHS, key=len, reverse=True))
_DAY_ALT = "|".join(WEEKDAYS)
_NUM_ALT = "|".join(sorted(_NUMBER_WORDS, key=len, reverse=True)) + r"|\d+"


def _rx(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.I)


_HALF_RE = _rx(r"\bin\s+half\s+an?\s+hour\b")
_REL_RE = _rx(rf"\b(?:in|after)\s+({_NUM_ALT})\s+(minute|min|hour|hr|day|week|month)s?\b")

_DATE_RULES: list[tuple[str, re.Pattern]] = [
    ("iso", _rx(rf"{_PFX}\b(\d{{4}})-(\d{{2}})-(\d{{2}})\b")),
    ("slash", _rx(rf"{_PFX}(?<![\d/])(\d{{1,2}})/(\d{{1,2}})(?:/(\d{{2,4}}))?(?![\d/])")),
    ("dayafter", _rx(rf"{_PFX}\bday\s+after\s+tomorrow\b")),
    ("tomorrow", _rx(rf"{_PFX}\btomorrow\b")),
    ("tonight", _rx(rf"{_PFX}\btonight\b")),
    ("today", _rx(rf"{_PFX}\btoday\b")),
    ("eod", _rx(rf"{_PFX}\b(?:end\s+of\s+(?:the\s+)?day|eod)\b")),
    ("eow", _rx(rf"{_PFX}\b(?:end\s+of\s+(?:the\s+)?week|eow)\b")),
    ("nextweek", _rx(rf"{_PFX}\bnext\s+week\b")),
    ("nextmonth", _rx(rf"{_PFX}\bnext\s+month\b")),
    ("weekend", _rx(rf"{_PFX}\b(?:this\s+)?weekend\b")),
    ("weekday", _rx(rf"{_PFX}\b(?:(next|this|coming)\s+)?({_DAY_ALT})\b")),
    ("monthday", _rx(rf"{_PFX}\b({_MONTH_ALT})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?\b"
                     rf"(?!\s*(?:am|pm|a\.m|p\.m|:))")),
    ("daymonth", _rx(rf"{_PFX}\b(?:the\s+)?(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({_MONTH_ALT})\b")),
]

_AT = r"(?:\b(?:at|by|before|around|until)\s+|@\s*)?"
_TIME_AMPM = _rx(rf"{_AT}(?<![\d:])(\d{{1,2}})(?::(\d{{2}}))?\s*([ap])\.?m\b\.?")
_TIME_24 = _rx(rf"{_AT}(?<![\d:])([01]?\d|2[0-3]):([0-5]\d)(?![\d:])")
_TIME_AT = _rx(r"\b(?:at|by|before|around|until)\s+(\d{1,2})\b"
               r"(?![:/\d]|\s*(?:%|percent|dollars?|bucks|items?|things?|minutes?|mins?|"
               r"hours?|hrs?|days?|weeks?|months?|times?))")
_NOON = _rx(r"(?:\bat\s+)?\b(noon|midday|midnight)\b")
_TOD_PREFIXED = _rx(r"\b(?:in\s+the|this|early|late)\s+(morning|afternoon|evening|night)\b")
_TOD_BARE = _rx(r"\b(morning|afternoon|evening|night)\b")

_DANGLING = re.compile(
    r"(?:^|\s)(?:by|on|at|before|until|till|for|due|in|after|around|this|next|from|to|and|or)"
    r"[\s,.;:!?]*$", re.I)
_LEADING = re.compile(r"^(?:by|on|at|before|until|till|due|around|and|or)\s+", re.I)


def _cut(text: str, match: re.Match) -> str:
    """Remove a regex match from text (replaced by a space)."""
    return text[:match.start()] + " " + text[match.end():]


def _clean(text: str) -> str:
    """Normalise whitespace and strip prepositions left dangling by a removal."""
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    previous = None
    while previous != text:
        previous = text
        text = _DANGLING.sub("", text).strip()
        text = _LEADING.sub("", text).strip()
    return text.strip(" ,.;:-")


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _add_months(d: date, n: int) -> date:
    years, month0 = divmod(d.month - 1 + n, 12)
    year, month = d.year + years, month0 + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def _to_number(token: str) -> int:
    return int(token) if token.isdigit() else _NUMBER_WORDS[token.lower()]


def _upcoming(month: int, day: int, now: datetime) -> date | None:
    """Next occurrence of month/day (today or later): dateparser first, manual fallback."""
    found: date | None = None
    if dateparser is not None and 1 <= month <= 12:
        try:
            parsed = dateparser.parse(
                f"{day} {calendar.month_name[month]}",
                settings={"PREFER_DATES_FROM": "future", "RELATIVE_BASE": now})
            if parsed and parsed.month == month and parsed.day == day:
                found = parsed.date()
        except Exception:
            found = None
    if found is None:
        found = _safe_date(now.year, month, day)
        if found is not None and found < now.date():
            found = _safe_date(now.year + 1, month, day)
    if found is not None and found < now.date():
        found = _safe_date(found.year + 1, month, day)
    return found


def _resolve_date(kind: str, m: re.Match, now: datetime) -> tuple | None:
    """Return (date, default_time, forced_time) for a date match, or None if invalid."""
    today = now.date()
    default = config.DEFAULT_DEADLINE_TIME
    if kind == "iso":
        d = _safe_date(*(int(g) for g in m.groups()))
        return (d, default, None) if d else None
    if kind == "slash":
        month, day = int(m.group(1)), int(m.group(2))
        if m.group(3):
            year = int(m.group(3)) + (2000 if int(m.group(3)) < 100 else 0)
            d = _safe_date(year, month, day)
        else:
            d = _upcoming(month, day, now) if 1 <= month <= 12 else None
        return (d, default, None) if d else None
    if kind == "dayafter":
        return today + timedelta(days=2), default, None
    if kind == "tomorrow":
        return today + timedelta(days=1), default, None
    if kind == "tonight":
        return today, None, config.PART_OF_DAY_TIMES["night"]
    if kind == "today":
        return today, None, None
    if kind == "eod":
        return today, None, (config.EOD_TIME if now.hour < config.EOD_TIME[0] else (23, 59))
    if kind == "eow":
        return today + timedelta(days=(4 - today.weekday()) % 7), None, config.EOD_TIME
    if kind == "nextweek":
        return today + timedelta(days=7), default, None
    if kind == "nextmonth":
        return _add_months(today, 1), default, None
    if kind == "weekend":
        return today + timedelta(days=(5 - today.weekday()) % 7), (10, 0), None
    if kind == "weekday":
        modifier = (m.group(1) or "").lower()
        wd = WEEKDAYS[m.group(2).lower()]
        if modifier == "next":  # "next Friday" = Friday of next calendar week
            d = today + timedelta(days=7 - today.weekday()) + timedelta(days=wd)
        else:
            delta = (wd - today.weekday()) % 7
            if delta == 0 and modifier != "this":
                delta = 7
            d = today + timedelta(days=delta)
        return d, default, None
    if kind in ("monthday", "daymonth"):
        month_token, day_token = (m.group(1), m.group(2)) if kind == "monthday" else (m.group(2), m.group(1))
        d = _upcoming(MONTHS[month_token.lower()], int(day_token), now)
        return (d, default, None) if d else None
    return None


def _try_date(work: str, now: datetime) -> tuple[date | None, tuple | None, tuple | None, str]:
    for kind, rx in _DATE_RULES:
        m = rx.search(work)
        if not m:
            continue
        resolved = _resolve_date(kind, m, now)
        if resolved is None:
            continue
        d, default_t, forced_t = resolved
        return d, default_t, forced_t, _cut(work, m)
    return None, None, None, work


def _try_time(work: str, has_date: bool) -> tuple[tuple[int, int] | None, str]:
    m = _TIME_AMPM.search(work)
    if m:
        hour, minute, meridiem = int(m.group(1)), int(m.group(2) or 0), m.group(3).lower()
        if 1 <= hour <= 12 and minute < 60:
            return (hour % 12 + (12 if meridiem == "p" else 0), minute), _cut(work, m)
    m = _TIME_24.search(work)
    if m:
        return (int(m.group(1)), int(m.group(2))), _cut(work, m)
    m = _TIME_AT.search(work)
    if m:
        hour = int(m.group(1))
        if 0 <= hour <= 23:
            if 1 <= hour <= 7:  # "at 5" almost always means 5 pm
                hour += 12
            return (hour, 0), _cut(work, m)
    m = _NOON.search(work)
    if m:
        return ((12, 0) if m.group(1).lower() in ("noon", "midday") else (23, 59)), _cut(work, m)
    m = _TOD_PREFIXED.search(work) or (_TOD_BARE.search(work) if has_date else None)
    if m:
        return config.PART_OF_DAY_TIMES[m.group(1).lower()], _cut(work, m)
    return None, work


def _extract(original: str, now: datetime | None) -> tuple[datetime | None, str]:
    if not original.strip():
        return None, original.strip()
    now = (now or datetime.now()).replace(microsecond=0)
    work = original
    rel_delta: timedelta | None = None
    date_val: date | None = None
    default_t: tuple[int, int] | None = None
    forced_t: tuple[int, int] | None = None

    m = _HALF_RE.search(work)
    if m:
        rel_delta, work = timedelta(minutes=30), _cut(work, m)
    else:
        m = _REL_RE.search(work)
        if m:
            n, unit = _to_number(m.group(1)), m.group(2).lower()
            work = _cut(work, m)
            if unit in ("minute", "min"):
                rel_delta = timedelta(minutes=n)
            elif unit in ("hour", "hr"):
                rel_delta = timedelta(hours=n)
            else:
                if unit == "day":
                    date_val = (now + timedelta(days=n)).date()
                elif unit == "week":
                    date_val = (now + timedelta(weeks=n)).date()
                else:
                    date_val = _add_months(now.date(), n)
                default_t = (now.hour, now.minute)

    if rel_delta is None and date_val is None:
        date_val, default_t, forced_t, work = _try_date(work, now)

    time_val: tuple[int, int] | None = None
    if rel_delta is None:
        time_val, work = _try_time(work, has_date=date_val is not None)

    if rel_delta is not None:
        deadline = now + rel_delta
    else:
        chosen = time_val or forced_t
        if date_val is None and chosen is None:
            return None, original.strip()
        if date_val is None:
            deadline = datetime.combine(now.date(), time(*chosen))
            if deadline <= now:
                deadline += timedelta(days=1)
        else:
            chosen = chosen or default_t or (
                config.EOD_TIME if now.hour < config.EOD_TIME[0] else (23, 59))
            deadline = datetime.combine(date_val, time(*chosen))
    return deadline, _clean(work)


def extract_deadline(text: str, now: datetime | None = None) -> tuple[datetime | None, str]:
    """Find a deadline in `text`; return (deadline | None, text with the time phrase removed).

    Never raises: any failure yields (None, original text).
    """
    original = text if isinstance(text, str) else ""
    try:
        return _extract(original, now)
    except Exception:
        return None, original.strip()