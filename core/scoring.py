"""Interaction Score (0-100): how effectively the user works with the assistant.

Weights: completion 35, voice success 25, confidence 15, streak 15 (cap 7 days),
overdue-inverse 10 (fewer overdue tasks is better).
"""
from __future__ import annotations

import math

from core import config

WEIGHTS = {"completion": 35.0, "voice_success": 25.0, "confidence": 15.0,
           "streak": 15.0, "overdue": 10.0}
NO_DATA_LABEL = "Say something to begin"

# (min_score, level, colour, tagline), highest first
_TIERS = [
    (75, "Hyper-Productive", "#39ff14", "Unstoppable. Keep the streak alive."),
    (50, "In Flow", "#ffb300", "You're in the zone."),
    (25, "Warming Up", "#00e5ff", "Building momentum."),
    (0, "Dormant", "#8b5cf6", "Give me a command to wake things up."),
]


def _num(stats: dict, key: str) -> float:
    """Read a finite float from stats; anything else counts as 0."""
    try:
        value = float(stats.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0.0
    return value if math.isfinite(value) else 0.0


def _unit(value: float) -> float:
    return max(0.0, min(1.0, value))


def interaction_score(stats: dict) -> dict:
    """Return {score:int 0-100, level, label, color, breakdown}.

    `level` is the tier name (Dormant / Warming Up / In Flow / Hyper-Productive);
    `label` is a short tagline, or "Say something to begin" when there is no data yet.
    """
    stats = stats if isinstance(stats, dict) else {}
    total, done = _num(stats, "total"), _num(stats, "done")
    if _num(stats, "interactions") <= 0 and total <= 0:
        return {"score": 0, "level": "Dormant", "label": NO_DATA_LABEL, "color": _TIERS[-1][2],
                "breakdown": {name: 0.0 for name in WEIGHTS}}

    pending = _num(stats, "pending") if "pending" in stats else max(total - done, 0.0)
    overdue_ratio = _unit(_num(stats, "overdue") / max(pending, 1.0))
    parts = {
        "completion": _unit(done / total) if total > 0 else 0.0,
        "voice_success": _unit(_num(stats, "success_rate")),
        "confidence": _unit(_num(stats, "avg_confidence")),
        "streak": _unit(_num(stats, "streak_days") / config.STREAK_SATURATION_DAYS),
        "overdue": 1.0 - overdue_ratio,
    }
    points = {name: parts[name] * WEIGHTS[name] for name in WEIGHTS}
    score = int(round(max(0.0, min(100.0, sum(points.values())))))
    _, level, color, tagline = next(tier for tier in _TIERS if score >= tier[0])
    return {"score": score, "level": level, "label": tagline, "color": color,
            "breakdown": {name: round(value, 1) for name, value in points.items()}}