from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from application.autonomy.autonomy_decision_step import AutonomyDecisionStep
from execution.capability_aware_planning import CapabilityPlanDecision


@dataclass(frozen=True)
class _Decision:
    decision_id: str = 'dec-1'
    action: str = 'launch_campaign'
    payload: dict[str, Any] = field(default_factory=dict)
    correlation_id: str = 'corr-1'


@dataclass(frozen=True)
class _Envelope:
    decision: _Decision = field(default_factory=_Decision)


@dataclass(frozen=True)
class _WorldState:
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class _Explanation:
    policy_id: str = 'policy-1'
    summary: str = 'ok'
    factors: tuple[str, ...] = ()


class _DecisionCore:
    def optimize(self, state: Any) -> _Envelope:
        return _Envelope()


class _PolicyExplainer:
    def explain(self, *, state: Any, envelope: Any) -> _Explanation:
        return _Explanation()


class _Planner:
    def plan_action(self, *, request: Any, state: Any, action_type: str, payload: dict[str, Any]) -> CapabilityPlanDecision:
        return CapabilityPlanDecision(
            action_type=action_type,
            payload_patch={'policy_verdict': {'allowed': False, 'reason': 'action_type_disabled_by_policy'}},
            allowed=False,
            fallback_used=False,
            reason='action_type_disabled_by_policy',
            capability={'allowed': False},
        )


class _Contract:
    def __init__(self) -> None:
        self._decision_core = _DecisionCore()
        self._policy_explainer = _PolicyExplainer()
        self._capability_aware_planner = _Planner()


@dataclass(frozen=True)
class _Request:
    tenant_id: str = 'tenant-1'
    business_id: str = 'business-1'
    user_id: str = 'user-1'
    autonomy_tier: str = 'full_autonomy'
    channel: str = 'headless'
    approval_policy: dict[str, Any] = field(default_factory=dict)
    constraints: dict[str, Any] = field(default_factory=dict)
    economy: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)


def test_autonomy_decision_step_fails_closed_to_notify_owner_when_capability_blocked() -> None:
    step = AutonomyDecisionStep(contract=_Contract())
    executable_action = step._project_executable_action(request=_Request(), state=_WorldState(), envelope=_Envelope())
    assert executable_action.action_type == 'notify_owner'
    assert executable_action.payload['operator_required'] is True
    assert executable_action.payload['capability_blocked'] is True


class _FallbackPlanner:
    def plan_action(self, *, request: Any, state: Any, action_type: str, payload: dict[str, Any]) -> CapabilityPlanDecision:
        return CapabilityPlanDecision(
            action_type='notify_owner',
            payload_patch={
                'capability_planning': {
                    'fallback_used': True,
                    'reason': 'stale_evidence_notify_owner',
                },
                'execution_verdict': {'operator_required': True},
            },
            allowed=True,
            fallback_used=True,
            reason='stale_evidence_notify_owner',
            capability={'allowed': True, 'fallback_used': True},
        )


class _FallbackContract(_Contract):
    def __init__(self) -> None:
        super().__init__()
        self._capability_aware_planner = _FallbackPlanner()


def test_autonomy_decision_step_honors_capability_fallback_action_even_without_runtime_executor() -> None:
    step = AutonomyDecisionStep(contract=_FallbackContract())
    executable_action = step._project_executable_action(request=_Request(autonomy_tier='bounded_autonomy'), state=_WorldState(), envelope=_Envelope())
    assert executable_action.action_type == 'notify_owner'
    assert executable_action.payload['execution_verdict']['operator_required'] is True
