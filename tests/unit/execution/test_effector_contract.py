from __future__ import annotations

from execution.effectors.router import EffectorRouter
from execution.runners.ads.launch_campaign import Runner as LaunchCampaignRunner


def test_effector_router_returns_verified_connector_metadata() -> None:
    router = EffectorRouter()
    result = router.execute(
        action_type="create_landing_page",
        action={
            "action_id": "a-1",
            "channel": "web",
            "decision_id": "d-1",
            "correlation_id": "c-1",
            "payload": {"slug": "cleaning-amsterdam"},
        },
    )
    assert result.attempted is True
    assert result.external_system == "site"
    assert result.code == "not_configured"
    assert result.operator_required is True
    assert result.evidence["connector_code"] == "not_configured"


def test_external_runner_returns_action_result_with_effector_payload() -> None:
    runner = LaunchCampaignRunner()
    result = runner.run(
        {
            "action_id": "a-2",
            "channel": "ads",
            "decision_id": "d-2",
            "correlation_id": "c-2",
            "payload": {"budget": 50},
        }
    )
    assert result.status == "operator_required"
    assert result.payload["action_type"] == "launch_campaign"
    assert result.payload["effector"]["external_system"] == "google_ads"
    assert result.payload["effector"]["code"] == "not_configured"
