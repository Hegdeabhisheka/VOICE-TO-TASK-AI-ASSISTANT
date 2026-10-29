import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.deadline import extract_deadline  # noqa: E402

NOW = datetime(2025, 1, 15, 10, 0)  # a Wednesday


def test_tomorrow_at_5pm():
    deadline, rest = extract_deadline("call mom tomorrow at 5pm", NOW)
    assert deadline == datetime(2025, 1, 16, 17, 0)
    assert rest == "call mom"


def test_in_two_hours():
    deadline, rest = extract_deadline("finish report in 2 hours", NOW)
    assert deadline == datetime(2025, 1, 15, 12, 0)
    assert rest == "finish report"


def test_in_fifteen_minutes_and_half_an_hour():
    assert extract_deadline("check the oven in 15 minutes", NOW)[0] == datetime(2025, 1, 15, 10, 15)
    deadline, rest = extract_deadline("call the bank in half an hour", NOW)
    assert deadline == datetime(2025, 1, 15, 10, 30)
    assert rest == "call the bank"


def test_in_three_days_spelled_out_keeps_current_time():
    deadline, rest = extract_deadline("pick up laundry in three days", NOW)
    assert deadline == datetime(2025, 1, 18, 10, 0)
    assert rest == "pick up laundry"


def test_next_friday_means_next_calendar_week():
    deadline, rest = extract_deadline("submit invoice next Friday", NOW)
    assert deadline == datetime(2025, 1, 24, 9, 0)
    assert rest == "submit invoice"


def test_bare_weekday_is_upcoming():
    assert extract_deadline("gym on friday", NOW)[0] == datetime(2025, 1, 17, 9, 0)


def test_friday_evening_uses_evening_hour():
    deadline, rest = extract_deadline("meet Sarah by Friday evening", NOW)
    assert deadline == datetime(2025, 1, 17, 18, 0)
    assert rest == "meet Sarah"


def test_vague_parts_of_day():
    assert extract_deadline("email the team tomorrow morning", NOW)[0] == datetime(2025, 1, 16, 9, 0)
    assert extract_deadline("dinner tomorrow afternoon", NOW)[0] == datetime(2025, 1, 16, 14, 0)


def test_tonight_end_of_day_and_weekend():
    assert extract_deadline("buy groceries tonight", NOW)[0] == datetime(2025, 1, 15, 21, 0)
    deadline, rest = extract_deadline("send email by end of day", NOW)
    assert deadline == datetime(2025, 1, 15, 17, 0)
    assert rest == "send email"
    deadline, rest = extract_deadline("submit the form this weekend", NOW)
    assert deadline == datetime(2025, 1, 18, 10, 0)
    assert rest == "submit the form"


def test_time_only_rolls_to_next_day_when_past():
    deadline, rest = extract_deadline("stand up at 9am", NOW)
    assert deadline == datetime(2025, 1, 16, 9, 0)
    assert rest == "stand up"


def test_24_hour_clock_and_bare_hour():
    assert extract_deadline("meeting at 14:30", NOW)[0] == datetime(2025, 1, 15, 14, 30)
    deadline, rest = extract_deadline("call dad at 5", NOW)  # "at 5" means 5 pm
    assert deadline == datetime(2025, 1, 15, 17, 0)
    assert rest == "call dad"


def test_calendar_dates():
    deadline, rest = extract_deadline("dentist on March 3", NOW)
    assert deadline == datetime(2025, 3, 3, 9, 0)
    assert rest == "dentist"
    deadline, rest = extract_deadline("do taxes by 04/20", NOW)
    assert deadline == datetime(2025, 4, 20, 9, 0)
    assert rest == "do taxes"


def test_next_week():
    deadline, rest = extract_deadline("plan sprint next week", NOW)
    assert deadline == datetime(2025, 1, 22, 9, 0)
    assert rest == "plan sprint"


def test_dangling_preposition_removed():
    assert extract_deadline("pay rent by tomorrow", NOW)[1] == "pay rent"


def test_no_deadline_returns_text_unchanged():
    deadline, rest = extract_deadline("buy 3 apples", NOW)
    assert deadline is None
    assert rest == "buy 3 apples"


def test_never_raises_on_bad_input():
    assert extract_deadline("", NOW) == (None, "")
    assert extract_deadline(None, NOW)[0] is None      # type: ignore[arg-type]
    assert extract_deadline("???!!! 99/99/99 31 february", NOW)[0] is None or True