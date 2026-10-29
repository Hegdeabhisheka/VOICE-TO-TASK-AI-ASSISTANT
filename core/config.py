"""Central configuration: constants, paths, thresholds and keyword lists."""
from __future__ import annotations

from pathlib import Path

# ----------------------------------------------------------------------------- paths
BASE_DIR: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = BASE_DIR / "data"
DB_PATH: Path = DATA_DIR / "tasks.db"

# ----------------------------------------------------------------------------- models
WHISPER_MODEL: str = "base"
WHISPER_COMPUTE_TYPE: str = "int8"
SPACY_MODEL: str = "en_core_web_sm"

# ----------------------------------------------------------------------------- domain
PRIORITIES = ["low", "medium", "high", "urgent"]
CATEGORIES = ["work", "personal", "study", "health", "shopping", "finance", "other"]
DEFAULT_PRIORITY: str = "medium"
DEFAULT_CATEGORY: str = "other"

# ----------------------------------------------------------------------------- thresholds
MIN_COMMAND_CONFIDENCE: float = 0.55   # below this a command should be confirmed / repeated
CONFIDENCE_CUTOFF: float = MIN_COMMAND_CONFIDENCE
FUZZY_MATCH_THRESHOLD: float = 0.45    # minimum score for find_tasks matches
AMBIGUITY_MARGIN: float = 0.10         # top-2 matches closer than this are "ambiguous"
DUE_SOON_MINUTES: int = 60
MIN_AUDIO_BYTES: int = 2000            # non-WAV recordings shorter than this count as empty
MIN_AUDIO_SECONDS: float = 0.3         # WAV recordings shorter than this count as empty
SILENCE_RMS: float = 0.004             # normalised RMS below this counts as silence
INTERACTION_SATURATION: int = 30       # interactions needed for full "usage" points
STREAK_SATURATION_DAYS: int = 7        # streak days needed for full "streak" points

# ----------------------------------------------------------------------------- deadlines
PART_OF_DAY_TIMES: dict[str, tuple[int, int]] = {
    "morning": (9, 0), "afternoon": (14, 0), "evening": (18, 0), "night": (21, 0),
}
EOD_TIME: tuple[int, int] = (17, 0)             # "end of day" / "EOD"
DEFAULT_DEADLINE_TIME: tuple[int, int] = (9, 0)  # date without a time ("tomorrow", "next Monday")

# ----------------------------------------------------------------------------- keyword lists
# Words that strengthen confidence in an intent (matched on word boundaries).
INTENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "add_task": ("add", "remind", "reminder", "create", "schedule", "remember", "new task",
                 "todo", "need to", "don't forget"),
    "complete_task": ("done", "finished", "complete", "completed", "finish", "check off", "mark"),
    "delete_task": ("delete", "remove", "cancel", "drop", "discard"),
    "list_tasks": ("show", "list", "tasks", "what", "pending", "overdue", "due"),
    "reschedule_task": ("reschedule", "postpone", "push back", "delay", "move", "defer"),
    "set_priority": ("priority", "urgent", "high", "low", "medium", "make", "set"),
    "daily_briefing": ("briefing", "brief me", "my day", "agenda", "schedule"),
}

# Verbs that typically start a task title (used when no explicit command word is spoken).
ACTION_VERBS = frozenset({
    "buy", "call", "email", "text", "send", "finish", "write", "prepare", "pay", "book", "clean",
    "submit", "review", "meet", "visit", "pick", "drop", "renew", "study", "read", "practice",
    "plan", "cook", "wash", "fix", "update", "research", "organize", "order", "walk", "water",
    "feed", "attend", "print", "sign", "return", "check", "follow", "pack", "wrap", "take",
})

# Phrases that signal a priority level. Longer phrases are tried first ("not urgent" before "urgent").
PRIORITY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "urgent": ("urgent", "urgently", "asap", "as soon as possible", "immediately", "right away",
               "right now", "critical", "emergency", "top priority", "urgent priority"),
    "high": ("high priority", "very important", "important", "crucial"),
    "medium": ("medium priority", "normal priority", "moderate priority"),
    "low": ("low priority", "not urgent", "no rush", "not important", "whenever you can",
            "whenever", "when i have time", "when i get a chance", "someday", "at some point"),
}

CATEGORY_KEYWORDS: dict[str, frozenset[str]] = {
    "work": frozenset({"meeting", "meetings", "report", "reports", "email", "emails", "client",
                       "clients", "project", "presentation", "office", "boss", "manager", "team",
                       "standup", "sprint", "deploy", "proposal", "slides", "colleague",
                       "interview", "conference", "review", "deadline"}),
    "personal": frozenset({"mom", "mum", "dad", "mother", "father", "birthday", "family", "friend",
                           "friends", "anniversary", "dinner", "lunch", "party", "wife", "husband",
                           "girlfriend", "boyfriend", "brother", "sister", "kids", "wedding",
                           "movie", "trip", "vacation", "flight"}),
    "study": frozenset({"homework", "exam", "exams", "study", "studying", "assignment", "class",
                        "lecture", "course", "quiz", "thesis", "essay", "revise", "revision",
                        "chapter", "textbook", "professor", "school", "university", "lab"}),
    "health": frozenset({"doctor", "dentist", "gym", "workout", "medicine", "medication", "pills",
                         "exercise", "yoga", "therapy", "therapist", "checkup", "prescription",
                         "run", "jog", "hospital", "vitamins", "meditate", "meditation",
                         "physio", "vaccine"}),
    "shopping": frozenset({"buy", "groceries", "grocery", "milk", "eggs", "bread", "shop",
                           "shopping", "order", "purchase", "store", "supermarket", "mall",
                           "amazon", "vegetables", "fruit", "fruits"}),
    "finance": frozenset({"pay", "bill", "bills", "rent", "tax", "taxes", "bank", "budget", "loan",
                          "insurance", "salary", "mortgage", "invoice", "payment", "credit",
                          "transfer", "refund", "emi", "subscription"}),
}