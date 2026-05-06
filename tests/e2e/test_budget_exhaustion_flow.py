from __future__ import annotations
import pytest
from tests.e2e._headless_harness import ScenarioStep, build_harness, make_request

pytestmark = [pytest.mark.integration, pytest.mark.e2e]

def test_budget_exhaustion_flow_blocks_second_step_after_first_spend(tmp_path) -> None:
    harness = build_harness(tmp_path, scenario=[
        ScenarioStep(action_type="notify_owner", decision_payload={"estimated_cost": 0.10}, output={"verified": True, "external_refs": ["internal:1"]}),
        ScenarioStep(action_type="notify_owner", decision_payload={"estimated_cost": 0.10}, output={"verified": True, "external_refs": ["internal:2"]}),
    ])
    report = harness.run(make_request(goal="Spend until budget ends", max_steps=2, constraints={"max_run_cost": 0.15}, economy={"max_run_cost": 0.15}))
    assert len(report.steps) == 2
    assert report.steps[0].executed is True
    assert report.steps[1].executed is False
    assert report.steps[1].operator_required is True
    assert report.steps[1].feedback["autonomy_safety"]["reason"] in {"action_budget_exceeded", "bounded_autonomy_exceeded"}
