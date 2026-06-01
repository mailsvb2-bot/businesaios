from __future__ import annotations

import pytest

from tests.e2e._headless_harness import ScenarioStep, build_harness, make_request

pytestmark = [pytest.mark.integration, pytest.mark.e2e]

def test_capability_degradation_flow_falls_back_on_low_health_score(tmp_path) -> None:
    harness = build_harness(tmp_path, scenario=[ScenarioStep(action_type="create_listing", output={"verified": True, "goal_reached": True})], runtime_capabilities={"create_listing": {"enabled": True, "healthy": False, "health_score": 0.10}})
    for _ in range(3):
        harness.capability_health_service.update_after_step(tenant_id="tenant-1", capability_key="create_listing", feedback={"executed": False, "verified": False})
    report = harness.run(make_request(goal="Publish under degraded capability", max_steps=1, meta={"runtime_capabilities": {"create_listing": {"enabled": True, "healthy": False, "health_score": 0.10}}}))
    step = report.steps[0]
    assert step.action == "notify_owner"
    assert harness.executor.seen_actions == ["notify_owner"]
    assert step.payload["capability_fallback_reason"] == "low_health_score"
    assert report.final_feedback["capability_planning"]["fallback_used"] is True
