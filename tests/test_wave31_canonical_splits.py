from __future__ import annotations

from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_world_model_service_delegates_support() -> None:
    text = _read("core/world_model/service.py")
    assert "WorldModelStateAssembler" in text
    assert "WorldModelSnapshotSupport" in text
    assert "def _reject_build(" in text


def test_ads_rl_service_is_advisory_only_and_uses_support() -> None:
    text = _read("core/growth/ads/rl/service.py")
    assert '"note": "advisory_suggestion_only"' in text
    assert "suggestion_to_public" in text
    assert "report_to_public" in text


def test_ai_ceo_planner_remains_plan_only() -> None:
    text = _read("core/ai_ceo/planner.py")
    assert "DecisionCore remains the single issuer" in text
    assert "CEOPlanBuilder" in text
    assert "apply_policy_and_rank" in text


def test_ads_connector_shared_read_surface_used() -> None:
    for path in [
        "interfaces/ads/google_ads_connector.py",
        "interfaces/ads/tiktok_ads_connector.py",
    ]:
        text = _read(path)
        assert "list_campaigns_with_token" in text
        assert "fetch_metrics_with_token" in text
