from __future__ import annotations
import pytest
from tests.e2e._headless_harness import ScenarioStep, build_harness, make_request

pytestmark = [pytest.mark.integration, pytest.mark.e2e]

def test_economic_veto_flow_blocks_step_before_real_execution(tmp_path) -> None:
    harness = build_harness(tmp_path, scenario=[ScenarioStep(action_type="notify_owner", decision_payload={"estimated_cost": 0.10}, output={"verified": True})])
    report = harness.run(make_request(goal="Publish a listing under zero budget", max_steps=1, constraints={"max_run_cost": 0.05}, economy={"max_run_cost": 0.05}))
    step = report.steps[0]
    assert step.executed is False
    assert step.operator_required is True
    assert harness.executor.calls == 0
    assert report.final_feedback["operator_required"] is True
    assert report.final_feedback["blocked_by_policy"] is False
    assert step.feedback.get("autonomy_safety", {}).get("reason") in {"action_budget_exceeded", "bounded_autonomy_exceeded", None}
