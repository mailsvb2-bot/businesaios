from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core.ai import _reset_decision_core_singleton_for_tests


@pytest.fixture(autouse=True)
def clear_singleton():
    _reset_decision_core_singleton_for_tests()
    yield
    _reset_decision_core_singleton_for_tests()


def test_live_headless_decision_to_execution_reaches_safety_and_executor():
    from application.autonomy.autonomy_decision_step import AutonomyDecisionStep
    from application.autonomy.autonomy_execution_step import AutonomyExecutionStep
    from runtime.execution.executor_result import ExecutionResult

    @dataclass(frozen=True)
    class Decision:
        decision_id: str
        correlation_id: str
        action: str
        payload: dict

    @dataclass(frozen=True)
    class Envelope:
        decision: Decision

    class LiveOptimizeCore:
        def __init__(self):
            self.calls = []

        def optimize(self, state):
            self.calls.append(state)
            return Envelope(
                decision=Decision(
                    decision_id="decision-live",
                    correlation_id="correlation-live",
                    action="notify_owner",
                    payload={"source": "optimize-only"},
                )
            )

    class CapabilityPlan:
        allowed = True
        action_type = "notify_owner"
        payload_patch = {}
        fallback_used = False

        def to_dict(self):
            return {
                "allowed": True,
                "action_type": self.action_type,
                "payload_patch": {},
                "fallback_used": False,
            }

    class SafetyVerdict:
        allowed = True
        operator_required = False
        reason = "allowed"
        details = {
            "action_budget": {"allowed": True, "currency": "RUB"},
            "bounded_autonomy": {"allowed": True},
            "blast_radius_guard": {"allowed": True},
        }

        def to_dict(self):
            return {
                "allowed": True,
                "operator_required": False,
                "reason": self.reason,
                "details": dict(self.details),
            }

    class AuditRecord:
        def to_dict(self):
            return {"audit": "ok"}

    class SafetyBundle:
        def __init__(self):
            self.pre_execution_calls = []

        def evaluate_pre_execution(self, **kwargs):
            self.pre_execution_calls.append(kwargs)
            return SafetyVerdict()

        def build_policy_snapshot(self, **kwargs):
            return {"policy": "snapshot"}

        def build_audit_record(self, **kwargs):
            return AuditRecord()

    core = LiveOptimizeCore()
    safety = SafetyBundle()
    executor = SimpleNamespace(
        execute=Mock(
            return_value=ExecutionResult(
                ok=True,
                output={"attempted": True, "executed": True, "verified": True},
                decision_id="decision-live",
                correlation_id="correlation-live",
            )
        )
    )
    contract = SimpleNamespace(
        _decision_core=core,
        _policy_explainer=SimpleNamespace(
            explain=lambda **kwargs: SimpleNamespace(
                policy_id="policy-live",
                summary="single canonical decision path",
                factors=("explicit_issuer",),
            )
        ),
        _capability_aware_planner=SimpleNamespace(
            plan_action=lambda **kwargs: CapabilityPlan()
        ),
        _executor=executor,
        _autonomy_safety_bundle=safety,
        _event_log=None,
        _decision_keyring=None,
    )
    request = SimpleNamespace(
        tenant_id="tenant-live",
        business_id="business-live",
        user_id="user-live",
        autonomy_tier="supervised",
        approval_policy={},
        constraints={"max_spend_rub": 1000},
        economy={"currency": "RUB", "max_spend": 1000},
        meta={"previous_feedback": {}},
        channel="headless",
    )
    state = {"goal": "prove-live-path"}
    trace = SimpleNamespace(record=Mock())

    decision_artifacts = AutonomyDecisionStep(contract=contract).evaluate(
        request=request,
        state=state,
        trace=trace,
        step_index=0,
        attempt_index=0,
    )
    result = AutonomyExecutionStep(contract=contract).execute(
        request=request,
        executable_action=decision_artifacts.executable_action,
        envelope=decision_artifacts.envelope,
        autonomy_decision=decision_artifacts.autonomy_decision,
    )

    assert result.ok is True
    assert core.calls == [state]
    assert len(safety.pre_execution_calls) == 1
    safety_call = safety.pre_execution_calls[0]
    assert safety_call["request"].economy["currency"] == "RUB"
    assert safety_call["action_type"] == "notify_owner"
    executor.execute.assert_called_once()
    executed_envelope = executor.execute.call_args.args[0]
    assert executed_envelope.decision.payload["economy"] == request.economy
    assert executed_envelope.decision.payload["autonomy_safety"]["allowed"] is True
