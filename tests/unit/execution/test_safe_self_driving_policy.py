from __future__ import annotations

from dataclasses import dataclass, field

from execution.safe_self_driving import SafeSelfDrivingPolicy


@dataclass(frozen=True)
class _Req:
    autonomy_tier: str = "full_autonomy"
    constraints: dict = field(default_factory=dict)


@dataclass(frozen=True)
class _Step:
    status: str
    executed: bool
    verified: bool
    operator_required: bool


def test_safe_loop_downgrades_full_autonomy_after_unverified_chain() -> None:
    policy = SafeSelfDrivingPolicy()
    req = _Req(
        autonomy_tier="full_autonomy",
        constraints={"safe_loop_max_consecutive_unverified": 2},
    )
    steps = [
        _Step(status="executed", executed=True, verified=False, operator_required=False),
        _Step(status="executed", executed=True, verified=False, operator_required=False),
    ]
    decision = policy.evaluate(
        request=req,
        steps=steps,
        previous_feedback={},
        last_step=steps[-1],
        consecutive_failures=2,
    )
    assert decision.should_downgrade is True
    assert decision.should_stop is False
    assert decision.next_tier == "bounded_autonomy"


def test_non_consecutive_operator_handoffs_do_not_force_downgrade() -> None:
    policy = SafeSelfDrivingPolicy()
    req = _Req(
        autonomy_tier="full_autonomy",
        constraints={"safe_loop_max_consecutive_operator_handoffs": 2},
    )
    steps = [
        _Step(status="operator_required", executed=False, verified=False, operator_required=True),
        _Step(status="executed", executed=True, verified=True, operator_required=False),
        _Step(status="operator_required", executed=False, verified=False, operator_required=True),
    ]
    decision = policy.evaluate(
        request=req,
        steps=steps,
        previous_feedback={},
        last_step=steps[-1],
        consecutive_failures=0,
    )
    assert decision.should_downgrade is False
    assert decision.should_stop is False
