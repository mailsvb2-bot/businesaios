from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_growth_autopilot_engine_is_recommendation_only() -> None:
    path = ROOT / "core" / "growth" / "autopilot_engine.py"
    text = path.read_text(encoding="utf-8")
    assert "does not issue decisions" in text
    assert "does not apply ads changes directly" in text


def test_growth_proposal_service_stays_proposal_only() -> None:
    path = ROOT / "core" / "growth" / "proposal_service.py"
    text = path.read_text(encoding="utf-8")
    assert "must not apply policy directly" in text
    assert "must not emit actions on its own" in text


def test_marketing_composer_stays_composition_only() -> None:
    path = ROOT / "core" / "marketing" / "llm_composer.py"
    text = path.read_text(encoding="utf-8")
    assert 'DecisionCore decides, LLM composes.' in text
