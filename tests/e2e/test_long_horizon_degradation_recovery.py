from __future__ import annotations

import pytest

from tests.e2e._headless_harness import ScenarioStep, build_harness, make_request

pytestmark = [pytest.mark.integration, pytest.mark.e2e]


def test_long_horizon_degradation_then_recovery_keeps_one_owner_path(tmp_path) -> None:
    shared_root = tmp_path / "shared"

    degraded = build_harness(
        shared_root,
        scenario=[ScenarioStep(action_type="create_listing", output={"verified": True, "goal_reached": True})],
        runtime_capabilities={"create_listing": {"enabled": True, "healthy": False, "health_score": 0.10}},
    )
    for _ in range(3):
        degraded.capability_health_service.update_after_step(
            tenant_id="tenant-1",
            capability_key="create_listing",
            feedback={"executed": False, "verified": False},
        )
    degraded_report = degraded.run(
        make_request(
            goal="Recover degraded listing capability",
            max_steps=1,
            meta={"runtime_capabilities": {"create_listing": {"enabled": True, "healthy": False, "health_score": 0.10}}},
        )
    )
    assert degraded_report.steps[0].action == "notify_owner"
    assert degraded_report.final_feedback["capability_planning"]["fallback_used"] is True

    recovered = build_harness(
        shared_root,
        scenario=[ScenarioStep(action_type="create_listing", output={"verified": True, "goal_reached": True, "terminal": True, "external_refs": ["listing:recovered"]})],
        runtime_capabilities={"create_listing": {"enabled": True, "healthy": True, "health_score": 0.95}},
    )
    for _ in range(4):
        recovered.capability_health_service.update_after_step(
            tenant_id="tenant-1",
            capability_key="create_listing",
            feedback={"executed": True, "verified": True},
        )
    recovered_report = recovered.run(
        make_request(
            goal="Recover degraded listing capability",
            max_steps=1,
            meta={"runtime_capabilities": {"create_listing": {"enabled": True, "healthy": True, "health_score": 0.95}}},
            approval_policy={"allow_action_types": ["create_listing"]},
        )
    )

    assert recovered_report.steps[0].action == "create_listing"
    assert recovered_report.completed is True
    assert recovered_report.final_feedback["capability_planning"]["fallback_used"] is False
    owner_path = dict(recovered_report.final_feedback["owner_path"])
    assert owner_path["resumed_from_previous_run"] is True
    assert owner_path["observation_count"] >= 2
    assert owner_path["stage_observation_counts"]["routing"] >= 2
    assert owner_path["stage_observation_counts"]["verification"] >= 2
