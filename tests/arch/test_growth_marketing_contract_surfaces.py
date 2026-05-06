from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_growth_recommendation_contract_exists() -> None:
    path = ROOT / "core" / "growth" / "growth_recommendation_contract.py"
    text = path.read_text(encoding="utf-8")
    assert "class GrowthRecommendationPort" in text
    assert "GROWTH_RECOMMENDATION_CONTRACT_VERSION" in text


def test_marketing_composition_contract_exists() -> None:
    path = ROOT / "core" / "marketing" / "marketing_composition_contract.py"
    text = path.read_text(encoding="utf-8")
    assert "class MarketingCompositionPort" in text
    assert "MARKETING_COMPOSITION_CONTRACT_VERSION" in text
