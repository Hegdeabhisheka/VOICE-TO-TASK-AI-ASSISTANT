import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.scoring import NO_DATA_LABEL, interaction_score  # noqa: E402

PERFECT = {"total": 10, "done": 10, "pending": 0, "overdue": 0, "due_today": 0,
           "streak_days": 7, "interactions": 20, "avg_confidence": 1.0, "success_rate": 1.0}


def test_empty_stats_means_no_data():
    for stats in ({}, None, {"total": 0, "interactions": 0}):
        result = interaction_score(stats)  # type: ignore[arg-type]
        assert result["score"] == 0
        assert result["label"] == NO_DATA_LABEL
        assert result["level"] == "Dormant"


def test_perfect_stats_score_100_and_hyper_productive():
    result = interaction_score(PERFECT)
    assert result["score"] == 100
    assert result["level"] == "Hyper-Productive"
    assert result["color"] == "#39ff14"


def test_level_boundaries():
    assert interaction_score({"interactions": 1})["level"] == "Dormant"                      # 10
    base = {"interactions": 1, "success_rate": 1.0}
    assert interaction_score(base)["score"] == 35                                            # 25 + 10
    assert interaction_score(base)["level"] == "Warming Up"
    assert interaction_score({**base, "avg_confidence": 1.0})["level"] == "In Flow"          # 50
    assert interaction_score({**base, "avg_confidence": 1.0, "streak_days": 7})["score"] == 65


def test_scores_stay_between_0_and_100():
    samples = [{}, PERFECT, {"total": 5, "done": 0, "pending": 5, "overdue": 5, "interactions": 3},
               {"total": -5, "done": "x", "overdue": 999, "interactions": None, "success_rate": 7,
                "avg_confidence": -3, "streak_days": 1e9},
               {"total": float("nan"), "interactions": float("inf")}]
    for stats in samples:
        assert 0 <= interaction_score(stats)["score"] <= 100


def test_more_completed_tasks_never_lowers_score():
    scores = [interaction_score({"total": 10, "done": d, "pending": 10 - d, "interactions": 10,
                                 "success_rate": 0.8, "avg_confidence": 0.8})["score"]
              for d in range(11)]
    assert scores == sorted(scores) and scores[-1] > scores[0]


def test_more_overdue_tasks_never_raises_score():
    scores = [interaction_score({**PERFECT, "total": 10, "done": 6, "pending": 4, "overdue": o})["score"]
              for o in range(5)]
    assert scores == sorted(scores, reverse=True) and scores[0] > scores[-1]


def test_streak_is_capped_at_seven_days():
    seven = interaction_score({**PERFECT, "streak_days": 7})["score"]
    assert interaction_score({**PERFECT, "streak_days": 30})["score"] == seven
    assert interaction_score({**PERFECT, "streak_days": 0})["score"] < seven


def test_voice_success_and_confidence_raise_score():
    low = interaction_score({"interactions": 5, "success_rate": 0.2, "avg_confidence": 0.3})
    high = interaction_score({"interactions": 5, "success_rate": 0.9, "avg_confidence": 0.9})
    assert high["score"] > low["score"]


def test_result_shape_and_breakdown():
    result = interaction_score(PERFECT)
    assert set(result) == {"score", "level", "label", "color", "breakdown"}
    assert isinstance(result["score"], int)
    assert result["color"].startswith("#")
    assert set(result["breakdown"]) == {"completion", "voice_success", "confidence", "streak", "overdue"}
    assert abs(sum(result["breakdown"].values()) - 100) < 0.5