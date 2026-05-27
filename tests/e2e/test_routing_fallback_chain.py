from __future__ import annotations

import pytest

from tests.e2e._headless_harness import ScenarioStep, build_harness, make_request

pytestmark = [pytest.mark.integration, pytest.mark.e2e]

def test_routing_fallback_chain_degrades_to_notify_owner(tmp_path) -> None:
    harness = build_harness(tmp_path, scenario=[ScenarioStep(action_type="send_email", output={"verified": True, "goal_reached": True})], runtime_capabilities={"send_email": {"enabled": False, "healthy": False, "health_score": 0.0}})
    report = harness.run(make_request(goal="Reach out to the owner", max_steps=1, meta={"runtime_capabilities": {"send_email": {"enabled": False, "healthy": False, "health_score": 0.0}}}))
    step = report.steps[0]
    assert step.action == "notify_owner"
    assert harness.executor.seen_actions == ["notify_owner"]
    assert step.payload["capability_fallback_from"] == "send_email"
    assert step.payload["capability_fallback_reason"] == "communications_disabled"
    assert report.final_feedback["capability_planning"]["fallback_used"] is True
