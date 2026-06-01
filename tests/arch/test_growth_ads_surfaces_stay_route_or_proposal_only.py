from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def test_ads_autopilot_surface_stays_wrapper_only() -> None:
    path = ROOT / "core" / "growth" / "ads" / "ads_autopilot.py"
    text = path.read_text(encoding="utf-8")
    assert "Single, canonical Ads autopilot entrypoint." in text
    assert ".issue(" not in text

def test_ads_apply_route_is_route_only() -> None:
    path = ROOT / "runtime" / "handlers" / "ads_apply_route.py"
    text = path.read_text(encoding="utf-8")
    assert "extract_ads_apply_route" in text
    assert "DecisionCore->RuntimeExecutor->AdsApplyHandler" in text
    assert ".issue(" not in text

def test_ads_autopilot_route_is_route_only() -> None:
    path = ROOT / "runtime" / "handlers" / "ads_autopilot" / "route.py"
    text = path.read_text(encoding="utf-8")
    assert "extract_autopilot_route" in text
    assert "DecisionCore->RuntimeExecutor->AdsAutopilotHandler" in text
    assert ".issue(" not in text
