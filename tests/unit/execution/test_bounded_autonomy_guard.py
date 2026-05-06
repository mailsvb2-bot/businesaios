from __future__ import annotations

from dataclasses import dataclass, field

from execution.bounded_autonomy import BoundedAutonomyGuard


@dataclass(frozen=True)
class _Req:
    autonomy_tier: str = "bounded_autonomy"
    constraints: dict = field(default_factory=dict)
    economy: dict = field(default_factory=dict)
    approval_policy: dict = field(default_factory=dict)


def test_bounded_autonomy_blocks_budget_change_when_limit_exceeded() -> None:
    guard = BoundedAutonomyGuard()
    req = _Req(
        autonomy_tier="bounded_autonomy",
        constraints={"max_budget_change_total": 10.0},
    )
    decision = guard.evaluate(
        request=req,
        action_type="update_budget",
        payload={"budget_change_amount": 25.0},
        previous_feedback={},
    )
    assert decision.allowed is False
    assert decision.reason in {"bounded_autonomy_exceeded", "action_budget_exceeded"}
    assert "max_budget_change_total" in decision.details["violated_limits"]


def test_supervised_effectful_action_requires_operator() -> None:
    guard = BoundedAutonomyGuard()
    req = _Req(autonomy_tier="supervised")
    decision = guard.evaluate(
        request=req,
        action_type="launch_campaign",
        payload={"estimated_cost": 1.0},
        previous_feedback={},
    )
    assert decision.allowed is False
    assert decision.operator_required is True
    assert decision.reason == "bounded_autonomy_requires_operator"
