from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from execution.action_budget_engine import ActionBudgetDecision, ActionBudgetEngine


@dataclass(frozen=True)
class StubRequest:
    goal: str = "increase revenue"
    tenant_id: str = "tenant-1"
    business_id: str = "biz-1"
    autonomy_tier: str = "bounded_autonomy"
    economy: dict[str, Any] = field(default_factory=dict)
    constraints: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)


def test_action_budget_allows_step_within_limits() -> None:
    engine = ActionBudgetEngine()
    request = StubRequest(economy={"max_run_cost": 10.0, "max_total_cost": 20.0, "max_outbound_total": 10, "max_publications_total": 5, "max_irreversible_total": 3, "max_budget_change_total": 100.0})
    decision: ActionBudgetDecision = engine.evaluate(request=request, action_type="notify_owner", payload={"recipient_count": 2}, previous_feedback={"action_budget_state": {"spent_total": 1.0, "spent_this_run": 1.0}})
    assert decision.allowed is True
    assert decision.reason == "within_action_budget"
    assert decision.snapshot_after.spent_total >= decision.snapshot_before.spent_total
    assert decision.snapshot_after.outbound_total == decision.snapshot_before.outbound_total + 2


def test_action_budget_blocks_when_run_cost_exceeded() -> None:
    engine = ActionBudgetEngine()
    request = StubRequest(economy={"max_run_cost": 3.0, "max_total_cost": 50.0})
    decision = engine.evaluate(request=request, action_type="launch_campaign", payload={"estimated_cost": 4.5, "currency": "USD"}, previous_feedback={"action_budget_state": {"spent_total": 0.0, "spent_this_run": 0.0}})
    assert decision.allowed is False
    assert decision.reason == "action_budget_exceeded"
    assert "max_run_cost" in decision.violated_limits
