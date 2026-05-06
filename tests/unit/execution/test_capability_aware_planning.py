from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from execution.capability_aware_planning import CapabilityAwarePlanner


@dataclass(frozen=True)
class StubState:
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StubRequest:
    autonomy_tier: str = "bounded_autonomy"
    meta: dict[str, Any] = field(default_factory=dict)


def test_capability_planner_blocks_disabled_runtime_capability() -> None:
    planner = CapabilityAwarePlanner()
    state = StubState(meta={"runtime_capabilities": {"launch_campaign": {"enabled": False, "healthy": True}}})
    decision = planner.plan_action(request=StubRequest(), state=state, action_type="launch_campaign", payload={"estimated_cost": 2.0})
    assert decision.allowed is False
    assert decision.reason == "runtime_capability_disabled"


def test_capability_planner_falls_back_to_notify_owner_when_comms_disabled() -> None:
    planner = CapabilityAwarePlanner()
    state = StubState(meta={"runtime_capabilities": {"send_email": {"enabled": False, "healthy": True}}})
    decision = planner.plan_action(request=StubRequest(), state=state, action_type="send_email", payload={"recipient_count": 1})
    assert decision.allowed is True
    assert decision.fallback_used is True
    assert decision.action_type == "notify_owner"
    assert decision.reason == "capability_fallback_notify_owner"
