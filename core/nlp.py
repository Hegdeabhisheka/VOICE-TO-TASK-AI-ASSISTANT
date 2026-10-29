"""Intent + entity extraction: raw text -> ParsedCommand."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache

from core import config
from core.deadline import extract_deadline

INTENTS = ["add_task", "complete_task", "delete_task", "list_tasks",
           "reschedule_task", "set_priority", "daily_briefing", "unknown"]


@dataclass
class ParsedCommand:
    """Structured representation of one spoken/typed command."""
    intent: str
    title: str = ""
    deadline: datetime | None = None
    priority: str = "medium"
    category: str = "other"
    target_query: str = ""
    confidence: float = 0.0
    raw_text: str = ""


def _rx(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.I)


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


@lru_cache(maxsize=1)
def _get_spacy():
    """Load spaCy once; None when spaCy or the model is unavailable (regex fallback)."""
    try:
        import spacy
        return spacy.load(config.SPACY_MODEL)
    except Exception:
        return None


# ----------------------------------------------------------------------------- intents
_FILLER = _rx(r"^(?:(?:hey|hi|hello|ok|okay|yo)\b[,\s]*)?(?:(?:assistant|jarvis|computer)\b[,\s]*)?"
              r"(?:(?:please|kindly)\b[,\s]*)?(?:(?:can|could|would|will)\s+you\s+(?:please\s+)?)?"
              r"(?:i(?:\s+want|\s+would\s+like|'d\s+like)\s+you\s+to\s+)?")

_RE_ADD = _rx(r"^(?:add\b|create\b|insert\b|log\b|put\b|new\s+(?:task|todo|reminder)\b|task\s*[:\-]|"
              r"todo\s*[:\-]|remind\s+me\b|reminder\b|set\s+(?:a\s+)?reminder\b|schedule\b|"
              r"remember\b|don'?t\s+forget\b|note\s+(?:that|to)\b|write\s+down\b|jot\s+down\b|"
              r"make\s+(?:a|an)\s+(?:new\s+)?(?:task|todo|reminder|note)\b|"
              r"i\s+(?:need|have|must|should|gotta|got|want)\s+to\b|i\s+gotta\b|i'?ve\s+got\s+to\b)")
_RE_BRIEF = _rx(r"\b(?:daily\s+briefing|morning\s+briefing|brief\s+me|briefing|"
                r"(?:what(?:'s|\s+is)|how(?:'s|\s+is))\s+(?:on\s+)?my\s+(?:day|schedule|agenda)|"
                r"plan\s+(?:for\s+)?(?:my\s+)?day|what\s+do\s+i\s+have\s+(?:on\s+)?today|"
                r"summary\s+of\s+(?:my\s+)?(?:day|tasks))\b")
_RE_LIST = _rx(r"^(?:show|list|display|view|read|give\s+me|tell\s+me|what(?:'s|\s+is|\s+are)?|which|"
               r"how\s+many|do\s+i\s+have|any)\b.*\b(?:tasks?|todos?|to-?dos?|to\s+do|reminders?|list|"
               r"agenda|pending|overdue|due|schedule|deadlines?)\b|^what\s+do\s+i\s+have\b|"
               r"^(?:my\s+)?(?:tasks|todos|to-?do\s+list)\s*$")
_RE_PRIO_A = _rx(r"^(?:set|change|update|raise|lower|bump|increase|decrease|adjust)\b.*\bpriority\b")
_RE_PRIO_B = _rx(r"^(?:make|mark|set|flag)\b.*\b(?:low|medium|high|urgent|critical)"
                 r"(?:\s+priority)?\s*[.!]?$")
_RE_RESCHED = _rx(r"^(?:reschedule|postpone|push\s+back|push|delay|move|shift|defer)\b|"
                  r"^change\s+(?:the\s+)?(?:deadline|due\s+date|due\s+time|time)\b")
_RE_COMPLETE = _rx(r"^(?:complete|finish|finished|done\s+with|check\s+off|tick\s+off|cross\s+off)\b|"
                   r"^mark\b.*\b(?:done|complete|completed|finished)\s*[.!]?$|"
                   r"\b(?:is|are)\s+(?:done|complete|completed|finished)\s*[.!]?$|"
                   r"^i(?:'ve|\s+have)?\s+(?:just\s+)?(?:finished|completed|done)\b|"
                   r"^i(?:'m|\s+am)\s+done\s+with\b")
_RE_DELETE = _rx(r"^(?:delete|remove|cancel|drop|discard|trash|erase|clear|get\s+rid\s+of)\b")
_RE_CHITCHAT = _rx(r"^(?:hello|hi|hey|thanks?|thank\s+you|good\s+(?:morning|afternoon|evening|night)|"
                   r"how\s+are\s+you|what\s+can\s+you\s+do|help|test|testing)\b[\s.!?]*$")

_ORDERED_RULES: list[tuple[re.Pattern, str, float]] = [
    (_RE_ADD, "add_task", 0.88),
    (_RE_BRIEF, "daily_briefing", 0.92),
    (_RE_LIST, "list_tasks", 0.86),
    (_RE_PRIO_A, "set_priority", 0.86),
    (_RE_PRIO_B, "set_priority", 0.84),
    (_RE_RESCHED, "reschedule_task", 0.86),
    (_RE_COMPLETE, "complete_task", 0.86),
    (_RE_DELETE, "delete_task", 0.86),
]


def _normalize(text: str) -> str:
    """Strip wake words and politeness; fix curly quotes."""
    s = _squash((text or "").replace("\u2019", "'").replace("\u2018", "'"))
    previous = None
    while previous != s:
        previous = s
        s = _FILLER.sub("", s).strip()
    return s


def _keyword_confidence(intent: str, base: float, text: str) -> float:
    """Raise confidence for supporting keywords; lower it for rambling input."""
    low = text.lower()
    hits = sum(1 for kw in config.INTENT_KEYWORDS.get(intent, ())
               if re.search(rf"\b{re.escape(kw)}\b", low))
    conf = base + min(0.04, 0.02 * hits)
    if len(text.split()) > 30:
        conf -= 0.10
    return max(0.0, min(1.0, conf))


def _fallback_intent(t: str) -> tuple[str, float]:
    """No command pattern matched: treat as an implicit task if it looks like one."""
    words = t.split()
    if len(words) < 2:
        return "unknown", 0.2
    if words[0].lower() in config.ACTION_VERBS:
        return "add_task", 0.80
    nlp = _get_spacy()
    if nlp is not None:
        try:
            if any(tok.dep_ == "ROOT" and tok.pos_ == "VERB" for tok in nlp(t)):
                return "add_task", 0.62
        except Exception:
            pass
    return "add_task", 0.45  # probably mis-heard speech: stays below the confidence cutoff


def _detect_intent(t: str) -> tuple[str, float]:
    """Return (intent, confidence) from ordered rules, then keyword/verb/spaCy heuristics."""
    for pattern, intent, base in _ORDERED_RULES:
        if pattern.search(t):
            return intent, _keyword_confidence(intent, base, t)
    if _RE_CHITCHAT.match(t):
        return "unknown", 0.5
    intent, base = _fallback_intent(t)
    return intent, (_keyword_confidence(intent, base, t) if intent != "unknown" else base)


# ----------------------------------------------------------------------------- priority
_LEAD_WORDS = (r"it['’]?s|it\s+is|this\s+is|that['’]?s|is|as|with|marked\s+as|"
               r"mark\s+(?:it|this)\s+as|make\s+(?:it|this)|set\s+(?:it|this)\s+(?:to|as)")


def _build_priority_rules() -> list[tuple[str | None, re.Pattern]]:
    phrases = sorted(((p, lvl) for lvl, ps in config.PRIORITY_KEYWORDS.items() for p in ps),
                     key=lambda item: -len(item[0]))
    rules: list[tuple[str | None, re.Pattern]] = []
    for phrase, level in phrases:
        body = re.escape(phrase).replace("\\ ", r"[\s-]+")
        rules.append((level, _rx(rf"(?:\b(?:{_LEAD_WORDS})\s+)?\b{body}\b")))
    rules.append((None, _rx(r"\bpriority\s+(?:is\s+|of\s+|to\s+|as\s+|level\s+)?"
                            r"(low|medium|high|urgent|critical)\b")))
    return rules


_PRIORITY_RULES = _build_priority_rules()


def _extract_priority(text: str) -> tuple[str | None, str]:
    """Return (priority | None, text without the priority phrase)."""
    for fixed, pattern in _PRIORITY_RULES:
        m = pattern.search(text)
        if not m:
            continue
        level = (fixed or m.group(1)).lower()
        level = "urgent" if level == "critical" else level
        return level, _squash(text[:m.start()] + " " + text[m.end():])
    return None, text


# ----------------------------------------------------------------------------- category
_CAT_ALT = "|".join(config.CATEGORIES)
_CAT_EXPLICIT = [
    _rx(rf"\b(?:in|under|to|as|for)\s+(?:the\s+|my\s+|a\s+)?({_CAT_ALT})\s+"
        r"(?:category|list|tasks?|folder|project)\b"),
    _rx(rf"\bcategory\s*(?:is\s+|of\s+|:\s*)?({_CAT_ALT})\b"),
]


def _extract_explicit_category(text: str) -> tuple[str | None, str]:
    for pattern in _CAT_EXPLICIT:
        m = pattern.search(text)
        if m:
            return m.group(1).lower(), _squash(text[:m.start()] + " " + text[m.end():])
    return None, text


def _infer_category(text: str) -> str:
    """Keyword-based category; spaCy entity hint (PERSON/ORG) when nothing matches."""
    tokens = re.findall(r"[a-z]+", text.lower())
    scores = {cat: sum(1 for tok in tokens if tok in words)
              for cat, words in config.CATEGORY_KEYWORDS.items()}
    if scores:
        best = max(scores, key=lambda c: scores[c])
        if scores[best] > 0:
            return best
    nlp = _get_spacy()
    if nlp is not None and text.strip():
        try:
            labels = {ent.label_ for ent in nlp(text).ents}
            if "PERSON" in labels:
                return "personal"
            if "ORG" in labels:
                return "work"
        except Exception:
            pass
    return config.DEFAULT_CATEGORY


# ----------------------------------------------------------------------------- title cleanup
_ADD_PREFIXES = [_rx(p) for p in (
    r"^(?:add|create|insert|log|register|put|make)\s+(?:(?:a|an|the|my|new)\s+)*"
    r"(?:task|todo|to-do|to\s+do|item|reminder|note|entry)\b\s*"
    r"(?:to\s+(?:my\s+|the\s+)?(?:todo\s+list|to-do\s+list|task\s+list|list|tasks)\b\s*)?"
    r"(?:(?:called|named|titled|about|for|to|that)\b\s*)?[:\-]?\s*",
    r"^(?:add|put|insert|log|create)\b\s*(?:to\s+(?:my\s+|the\s+)?(?:todo\s+list|to-do\s+list|"
    r"task\s+list|list|tasks)\b\s*[:,\-]?\s*)?",
    r"^(?:remind\s+me|reminder)\b\s*(?:(?:to|about|that|of)\b\s*)?",
    r"^(?:schedule|set\s+(?:a\s+)?reminder)\b\s*(?:(?:a|an|the)\b\s*)?(?:(?:to|for|about)\b\s*)?",
    r"^(?:i\s+)?(?:need|have|must|want|should|gotta|ought)\s+to\b\s*|^(?:i'?ve\s+)?got\s+to\b\s*|"
    r"^i\s+gotta\b\s*",
    r"^(?:don'?t\s+forget|remember)\b\s*(?:(?:to|about)\b\s*)?",
    r"^(?:note|write\s+down|jot\s+down)\b\s*(?:(?:that|to)\b\s*)?",
    r"^(?:task|todo|to-do|reminder)\s*[:\-]\s*",
    r"^new\s+(?:task|todo|reminder)\b\s*[:\-]?\s*",
    r"^(?:to|that|about)\b\s+",
)]
_TRAILING_LIST = _rx(r"\s+(?:to|on|in|into)\s+(?:my|the)\s+(?:[\w-]+\s+)?"
                     r"(?:todo\s+list|to-do\s+list|task\s+list|list|tasks)\s*$")
_TRAILING_POLITE = _rx(r"[\s,]*(?:please|thanks|thank\s+you|for\s+me|ok|okay)\s*[.!]*$")


def _clean_title(text: str) -> str:
    """Remove command scaffolding ("remind me to", "add a task to") and capitalise."""
    s = _squash(text)
    for _ in range(4):
        before = s
        for pattern in _ADD_PREFIXES:
            s = pattern.sub("", s, count=1).strip()
        if s == before:
            break
    s = _TRAILING_LIST.sub("", s)
    s = _TRAILING_POLITE.sub("", s)
    s = s.strip(" ,.;:!?-\"'")
    return s[:1].upper() + s[1:] if s else ""


def _strip_task_words(text: str) -> str:
    """Remove leading articles/filler and trailing 'task' words from a target phrase."""
    s = _squash(text)
    previous = None
    while previous != s:
        previous = s
        s = re.sub(r"^(?:the|my|a|an|task|tasks|called|named|titled|that|reminder|item|off|up)\b\s*",
                   "", s, flags=re.I)
        s = re.sub(r"\s*\b(?:task|reminder|item)\s*[.!?]*$", "", s, flags=re.I)
        s = re.sub(r"\s*\b(?:from|off)\s+(?:my\s+|the\s+)?(?:todo\s+list|to-do\s+list|list|tasks)\s*[.!?]*$",
                   "", s, flags=re.I)
    return s.strip(" ,.;:!?-\"'")


# ----------------------------------------------------------------------------- builders
def _build_add(t: str, raw: str, now: datetime, conf: float) -> ParsedCommand:
    deadline, work = extract_deadline(t, now)
    priority, work = _extract_priority(work)
    explicit_cat, work = _extract_explicit_category(work)
    title = _clean_title(work)
    category = explicit_cat or _infer_category(title)
    if not title:
        conf = min(conf, 0.3)
    else:
        if title.split()[0].lower() in config.ACTION_VERBS:
            conf += 0.03  # verb match
        if deadline is not None:
            conf += 0.04
    return ParsedCommand("add_task", title, deadline, priority or config.DEFAULT_PRIORITY,
                         category, "", round(min(1.0, conf), 2), raw)


def _build_list(t: str, raw: str, now: datetime, conf: float) -> ParsedCommand:
    deadline, rest = extract_deadline(t, now)
    priority, rest = _extract_priority(rest)
    tokens = set(re.findall(r"[a-z]+", rest.lower()))
    category = next((c for c in config.CATEGORIES if c != "other" and c in tokens), "")
    return ParsedCommand("list_tasks", "", deadline, priority or "", category, "",
                         round(conf, 2), raw)


def _build_complete(t: str, raw: str, conf: float) -> ParsedCommand:
    q = re.sub(r"^(?:i(?:'ve|\s+have|'m|\s+am)?\s+(?:just\s+)?(?:finished|completed|done(?:\s+with)?)|"
               r"mark|complete|finish|finished|check\s+off|tick\s+off|cross\s+off|done\s+with)\b\s*",
               "", t, flags=re.I)
    q = re.sub(r"\s+(?:as\s+|is\s+|are\s+)?(?:done|complete|completed|finished)\s*[.!]?$", "", q, flags=re.I)
    q = _strip_task_words(q)
    return ParsedCommand("complete_task", target_query=q,
                         confidence=round(conf if q else 0.3, 2), raw_text=raw)


def _build_delete(t: str, raw: str, conf: float) -> ParsedCommand:
    q = re.sub(r"^(?:delete|remove|cancel|drop|discard|trash|erase|clear|get\s+rid\s+of)\b\s*",
               "", t, flags=re.I)
    q = _strip_task_words(q)
    return ParsedCommand("delete_task", target_query=q,
                         confidence=round(conf if q else 0.3, 2), raw_text=raw)


def _build_reschedule(t: str, raw: str, now: datetime, conf: float) -> ParsedCommand:
    deadline, rest = extract_deadline(t, now)
    q = re.sub(r"^(?:reschedule|postpone|push\s+back|push|delay|move|shift|defer)\b\s*", "", rest, flags=re.I)
    q = re.sub(r"^change\s+(?:the\s+)?(?:deadline|due\s+date|due\s+time|time)\s+(?:of|for)\s+", "", q, flags=re.I)
    q = re.sub(r"^(?:the\s+)?(?:deadline|due\s+date)\s+(?:of|for)\s+", "", q, flags=re.I)
    q = _strip_task_words(q)
    if not q or deadline is None:
        conf = min(conf, 0.5)
    return ParsedCommand("reschedule_task", deadline=deadline, target_query=q,
                         confidence=round(conf, 2), raw_text=raw)


def _build_set_priority(t: str, raw: str, conf: float) -> ParsedCommand:
    levels = re.findall(r"\b(low|medium|high|urgent|critical)\b", t.lower())
    priority = ("urgent" if levels[-1] == "critical" else levels[-1]) if levels else ""
    q = re.sub(r"^(?:set|change|update|raise|lower|bump|increase|decrease|adjust|make|mark|flag)\b\s*",
               "", t, flags=re.I)
    q = re.sub(r"^(?:the\s+)?(?:low|medium|high|urgent|critical)\s+priority\s+(?:for|on|of|to)\s+", "", q, flags=re.I)
    q = re.sub(r"\b(?:the\s+)?priority\s+(?:level\s+)?(?:of|for|on)?\s*", " ", q, flags=re.I)
    q = re.sub(r"\s*(?:as|to|at|is)?\s*(?:level\s+)?(?:low|medium|high|urgent|critical)"
               r"(?:\s+priority)?\s*[.!]?$", "", q, flags=re.I)
    q = _strip_task_words(q)
    if not priority or not q:
        conf = min(conf, 0.3)
    return ParsedCommand("set_priority", priority=priority, target_query=q,
                         confidence=round(conf, 2), raw_text=raw)


def _parse(t: str, raw: str, now: datetime) -> ParsedCommand:
    intent, conf = _detect_intent(t)
    if intent == "add_task":
        return _build_add(t, raw, now, conf)
    if intent == "list_tasks":
        return _build_list(t, raw, now, conf)
    if intent == "complete_task":
        return _build_complete(t, raw, conf)
    if intent == "delete_task":
        return _build_delete(t, raw, conf)
    if intent == "reschedule_task":
        return _build_reschedule(t, raw, now, conf)
    if intent == "set_priority":
        return _build_set_priority(t, raw, conf)
    return ParsedCommand(intent, confidence=round(conf, 2), raw_text=raw)


def parse_command(text: str, now: datetime | None = None) -> ParsedCommand:
    """Parse free text into a ParsedCommand. Never raises; failures yield intent 'unknown'."""
    raw = text if isinstance(text, str) else ""
    now = now or datetime.now()
    normalized = _normalize(raw)
    if not normalized:
        return ParsedCommand(intent="unknown", confidence=0.0, raw_text=raw)
    try:
        return _parse(normalized, raw, now)
    except Exception:
        return ParsedCommand(intent="unknown", confidence=0.0, raw_text=raw)