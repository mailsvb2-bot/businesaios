from __future__ import annotations
import pytest
from tests.e2e._assertions import assert_feedback_contract_shape
from tests.e2e._headless_harness import ScenarioStep, build_harness, make_request, seed_goal_plan

pytestmark = [pytest.mark.integration, pytest.mark.e2e]

def test_strategy_to_execution_preserves_goal_plan_context(tmp_path) -> None:
    harness = build_harness(tmp_path, scenario=[
        ScenarioStep(action_type="publish_service_page", output={"verified": True, "external_refs": ["seo:page:1"], "effector": {"verified": True, "external_ref": "seo:page:1"}})
    ])
    seed_goal_plan(harness, tenant_id="tenant-1", business_id="biz-1", goal="Expand service demand", plan_id="plan-1", next_focus="publish_service_page", remaining_action_hints=("publish_service_page", "request_review"))
    report = harness.run(make_request(goal="Expand service demand", max_steps=1, meta={"goal_id": "goal-expand-service-demand"}))
    step = report.steps[0]
    assert step.action == "publish_service_page"
    assert step.payload["goal_plan"]["plan_id"] == "plan-1"
    assert step.payload["goal_plan"]["next_focus"] == "publish_service_page"
    assert report.final_feedback["goal_plan"]["plan_id"] == "plan-1"
    assert_feedback_contract_shape(report.final_feedback)
