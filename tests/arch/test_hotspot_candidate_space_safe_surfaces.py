from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_growth_optimizer_has_score_surface() -> None:
    path = ROOT / "core" / "scorers" / "bandit.py"
    text = path.read_text(encoding="utf-8")
    assert "def score_bandit_arms" in text
    assert "thompson_score_only" in text


def test_growth_strategy_service_marks_ranking_as_advisory() -> None:
    path = ROOT / "core" / "growth" / "strategy" / "service.py"
    text = path.read_text(encoding="utf-8")
    assert "advisory_ranking_only" in text
    assert "next((" not in text


def test_creative_bandit_has_score_surface() -> None:
    path = ROOT / "core" / "growth" / "ads" / "creative" / "bandit.py"
    text = path.read_text(encoding="utf-8")
    assert "def score_all" in text
    assert "posterior_mean_score_only" in text


def test_capital_allocation_engine_has_score_options() -> None:
    path = ROOT / "core" / "economics" / "capital_allocation_engine.py"
    text = path.read_text(encoding="utf-8")
    assert "def score_options" in text
    assert "economics_recommendation_set_only" in text
