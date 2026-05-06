from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def test_ads_recommendation_contract_exists() -> None:
    path = ROOT / "core" / "growth" / "ads" / "ads_recommendation_contract.py"
    text = path.read_text(encoding="utf-8")
    assert "class AdsRecommendationPort" in text
    assert "ADS_RECOMMENDATION_CONTRACT_VERSION" in text

def test_ads_route_contract_exists() -> None:
    path = ROOT / "runtime" / "handlers" / "ads_route_contract.py"
    text = path.read_text(encoding="utf-8")
    assert "class StrictAdsRoutePort" in text
    assert "ADS_ROUTE_CONTRACT_VERSION" in text
