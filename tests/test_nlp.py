import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config, nlp  # noqa: E402
from core.nlp import INTENTS, parse_command  # noqa: E402

NOW = datetime(2025, 1, 15, 10, 0)  # a Wednesday


@pytest.fixture(autouse=True)
def _no_spacy(monkeypatch):
    """Keep tests deterministic: run the regex/keyword path regardless of spaCy being installed."""
    monkeypatch.setattr(nlp, "_get_spacy", lambda: None)


def test_add_with_deadline_and_category():
    cmd = parse_command("Add buy milk tomorrow at 5pm", NOW)
    assert cmd.intent == "add_task"
    assert cmd.title == "Buy milk"
    assert cmd.deadline == datetime(2025, 1, 16, 17, 0)
    assert cmd.category == "shopping"
    assert cmd.priority == "medium"
    assert cmd.confidence >= config.MIN_COMMAND_CONFIDENCE


def test_remind_me_with_priority_phrase():
    cmd = parse_command("Remind me to submit the report by Friday it's urgent", NOW)
    assert cmd.intent == "add_task"
    assert cmd.title == "Submit the report"
    assert cmd.priority == "urgent"
    assert cmd.category == "work"
    assert cmd.deadline == datetime(2025, 1, 17, 9, 0)


def test_comma_separated_priority_and_next_friday():
    cmd = parse_command("Add finish the quarterly report by next Friday, high priority", NOW)
    assert cmd.title == "Finish the quarterly report"
    assert cmd.priority == "high"
    assert cmd.deadline == datetime(2025, 1, 24, 9, 0)


def test_polite_filler_is_removed():
    cmd = parse_command("Hey assistant, can you please remind me to buy bread tomorrow at 6pm", NOW)
    assert (cmd.intent, cmd.title) == ("add_task", "Buy bread")
    assert cmd.deadline == datetime(2025, 1, 16, 18, 0)


def test_add_a_task_to_phrase_and_personal_category():
    cmd = parse_command("Please add a task to call the bank tomorrow", NOW)
    assert (cmd.intent, cmd.title, cmd.category) == ("add_task", "Call the bank", "finance")
    cmd = parse_command("remind me to call mom tomorrow at 5pm", NOW)
    assert (cmd.title, cmd.category) == ("Call mom", "personal")


def test_explicit_category_and_list_suffix():
    cmd = parse_command("add milk to my shopping list", NOW)
    assert cmd.title == "Milk"
    assert cmd.category == "shopping"


def test_no_deadline_and_trailing_punctuation():
    cmd = parse_command("add call the dentist", NOW)
    assert cmd.deadline is None
    assert (cmd.title, cmd.category) == ("Call the dentist", "health")
    assert parse_command("Add buy milk.", NOW).title == "Buy milk"


def test_relative_time_and_i_need_to():
    cmd = parse_command("remind me to take my medicine in 2 hours", NOW)
    assert (cmd.title, cmd.category) == ("Take my medicine", "health")
    assert cmd.deadline == datetime(2025, 1, 15, 12, 0)
    cmd = parse_command("I need to pay the electricity bill in 3 days", NOW)
    assert (cmd.title, cmd.category) == ("Pay the electricity bill", "finance")
    assert cmd.deadline == datetime(2025, 1, 18, 10, 0)


def test_vague_time_of_day_and_study_category():
    cmd = parse_command("add study for chemistry exam tomorrow morning", NOW)
    assert cmd.title == "Study for chemistry exam"
    assert cmd.category == "study"
    assert cmd.deadline == datetime(2025, 1, 16, 9, 0)


def test_schedule_meeting_is_work():
    cmd = parse_command("schedule a meeting with John on Monday at 10am", NOW)
    assert (cmd.intent, cmd.title, cmd.category) == ("add_task", "Meeting with John", "work")
    assert cmd.deadline == datetime(2025, 1, 20, 10, 0)


def test_priority_levels():
    assert parse_command("add clean the garage whenever", NOW).priority == "low"
    cmd = parse_command("I need to call the doctor asap", NOW)
    assert (cmd.title, cmd.priority, cmd.category) == ("Call the doctor", "urgent", "health")
    assert parse_command("add pay rent, not urgent", NOW).priority == "low"


def test_complete_variants():
    for text, target in [("mark buy milk as done", "buy milk"),
                         ("mark the report task as done", "report"),
                         ("I finished the quarterly report", "quarterly report"),
                         ("I'm done with the presentation", "presentation")]:
        cmd = parse_command(text, NOW)
        assert (cmd.intent, cmd.target_query) == ("complete_task", target), text


def test_delete_variants():
    for text, target in [("delete the dentist appointment", "dentist appointment"),
                         ("cancel my dentist appointment", "dentist appointment")]:
        cmd = parse_command(text, NOW)
        assert (cmd.intent, cmd.target_query) == ("delete_task", target), text


def test_list_and_briefing():
    assert parse_command("show me my tasks", NOW).intent == "list_tasks"
    assert parse_command("show overdue tasks", NOW).intent == "list_tasks"
    assert parse_command("give me my daily briefing", NOW).intent == "daily_briefing"
    listing = parse_command("what's due today", NOW)
    assert listing.intent == "list_tasks" and listing.deadline.date() == NOW.date()
    urgent = parse_command("list my urgent tasks", NOW)
    assert (urgent.intent, urgent.priority) == ("list_tasks", "urgent")


def test_reschedule():
    cmd = parse_command("reschedule the report to Monday at 3pm", NOW)
    assert (cmd.intent, cmd.target_query) == ("reschedule_task", "report")
    assert cmd.deadline == datetime(2025, 1, 20, 15, 0)
    cmd = parse_command("push back the report to next week", NOW)
    assert (cmd.intent, cmd.target_query) == ("reschedule_task", "report")
    assert cmd.deadline == datetime(2025, 1, 22, 9, 0)


def test_set_priority():
    cmd = parse_command("set priority of dentist appointment to high", NOW)
    assert (cmd.intent, cmd.priority, cmd.target_query) == ("set_priority", "high", "dentist appointment")
    cmd = parse_command("make the tax form urgent", NOW)
    assert (cmd.intent, cmd.priority, cmd.target_query) == ("set_priority", "urgent", "tax form")


def test_misheard_text_still_yields_a_task_with_clean_deadline():
    cmd = parse_command("remind me to by milk tomorrow", NOW)  # "buy" heard as "by"
    assert cmd.intent == "add_task"
    assert "milk" in cmd.title.lower()
    assert cmd.deadline == datetime(2025, 1, 16, 9, 0)


def test_gibberish_has_low_confidence_or_is_unknown():
    assert parse_command("uh um", NOW).confidence < config.MIN_COMMAND_CONFIDENCE
    assert parse_command("asdf", NOW).intent == "unknown"
    assert parse_command("hello", NOW).intent == "unknown"
    assert parse_command("", NOW).intent == "unknown"


def test_missing_title_or_target_lowers_confidence():
    assert parse_command("remind me", NOW).confidence <= 0.3
    assert parse_command("delete", NOW).confidence <= 0.3


def test_always_returns_valid_intent():
    for text in ["???", "asdf", "   ", "a" * 500, "add", "remind me", "mark", "set priority", None]:
        cmd = parse_command(text, NOW)  # type: ignore[arg-type]
        assert cmd.intent in INTENTS
        assert 0.0 <= cmd.confidence <= 1.0