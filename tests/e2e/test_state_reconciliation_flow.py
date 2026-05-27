from __future__ import annotations

import pytest

from tests.e2e._headless_harness import ScenarioStep, build_harness, make_request, seed_goal_plan

pytestmark = [pytest.mark.integration, pytest.mark.e2e]

def test_state_reconciliation_flow_persists_joined_contexts(tmp_path) -> None:
    harness = build_harness(tmp_path, scenario=[ScenarioStep(action_type="notify_owner", output={"verified": True, "external_refs": ["internal:1"]})])
    seed_goal_plan(harness, tenant_id="tenant-1", business_id="biz-1", goal="Grow local demand", plan_id="plan-reconcile", next_focus="notify_owner", remaining_action_hints=("notify_owner",))
    harness.performance_service.update_after_step(tenant_id="tenant-1", business_id="biz-1", goal="Grow local demand", feedback={"executed": True, "verified": True})
    harness.multi_goal_service.add_goal(tenant_id="tenant-1", business_id="biz-1", goal_id="goal-main", goal="Grow local demand", priority=90, urgency=80)
    report = harness.run(make_request(goal="Grow local demand", max_steps=1, meta={"goal_id": "goal-main"}))
    ledger = harness.read_single_ledger_record()
    snapshot = harness.read_latest_state_snapshot(ledger["run_id"])
    assert snapshot["goal_plan"]["plan_id"] == "plan-reconcile"
    assert snapshot["performance_learning"]["verification_rate"] >= 1.0
    assert any(item["goal_id"] == "goal-main" for item in snapshot["multi_goal"]["queue"])
    assert report.final_feedback["goal_plan"]["plan_id"] == "plan-reconcile"
