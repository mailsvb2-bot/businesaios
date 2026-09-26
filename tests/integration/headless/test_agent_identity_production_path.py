from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from application.autonomy.autonomy_decision_step import AutonomyDecisionStep
from application.autonomy.autonomy_execution_step import AutonomyExecutionStep
from application.business_autonomy.registry import AgentIdentityRegistry
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.execution.executor_result import ExecutionResult


class MemoryEventStore:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def append_event(self, event: dict) -> None:
        self.events.append(dict(event))

    def iter_events(self, *, tenant_id: str, start_ms: int, end_ms=None, user_id=None, event_type=None):
        del user_id
        for event in self.events:
            if str(event.get("tenant_id") or "") != str(tenant_id):
                continue
            if int(event.get("timestamp_ms") or 0) < int(start_ms):
                continue
            if end_ms is not None and int(event.get("timestamp_ms") or 0) > int(end_ms):
                continue
            if event_type is not None and str(event.get("event_type") or "") != str(event_type):
                continue
            yield dict(event)


def _registry() -> AgentIdentityRegistry:
    return AgentIdentityRegistry(
        event_store=MemoryEventStore(),
        idempotency_store=InMemoryIdempotencyStore(),
    )


@dataclass(frozen=True)
class Decision:
    decision_id: str
    correlation_id: str
    action: str
    payload: dict
    issuer_id: str


@dataclass(frozen=True)
class Envelope:
    decision: Decision


class Core:
    def __init__(self, *, issuer_id: str) -> None:
        self.issuer_id = issuer_id

    def optimize(self, state):
        del state
        return Envelope(
            Decision(
                decision_id="decision-agent",
                correlation_id="correlation-agent",
                action="notify_owner",
                payload={},
                issuer_id=self.issuer_id,
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
    details = {}

    def to_dict(self):
        return {
            "allowed": True,
            "operator_required": False,
            "reason": self.reason,
            "details": {},
        }


class AuditRecord:
    def to_dict(self):
        return {"audit": "ok"}


class SafetyBundle:
    def evaluate_pre_execution(self, **kwargs):
        del kwargs
        return SafetyVerdict()

    def build_policy_snapshot(self, **kwargs):
        del kwargs
        return {"policy": "snapshot"}

    def build_audit_record(self, **kwargs):
        del kwargs
        return AuditRecord()


def _contract(*, registry: AgentIdentityRegistry, issuer_id: str, executor) -> SimpleNamespace:
    return SimpleNamespace(
        _decision_core=Core(issuer_id=issuer_id),
        _policy_explainer=SimpleNamespace(
            explain=lambda **kwargs: SimpleNamespace(
                policy_id="policy-agent",
                summary="agent identity path",
                factors=(),
            )
        ),
        _capability_aware_planner=SimpleNamespace(plan_action=lambda **kwargs: CapabilityPlan()),
        _executor=executor,
        _autonomy_safety_bundle=SafetyBundle(),
        _event_log=None,
        _decision_keyring=None,
        _agent_identity_registry=registry,
    )


def _request(*, agent_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        tenant_id="tenant-agent",
        business_id="business-agent",
        user_id="user-agent",
        agent_id=agent_id,
        autonomy_tier="supervised",
        approval_policy={},
        constraints={},
        economy={},
        meta={"previous_feedback": {}},
        channel="headless",
        goal_id=None,
    )


def test_agent_bound_decision_fails_closed_before_intent_when_unprovisioned() -> None:
    registry = _registry()
    executor = SimpleNamespace(execute=Mock())
    contract = _contract(registry=registry, issuer_id="child-agent", executor=executor)

    with pytest.raises(LookupError):
        AutonomyDecisionStep(contract=contract).evaluate(
            request=_request(agent_id="child-agent"),
            state={},
            trace=SimpleNamespace(record=Mock()),
            step_index=0,
            attempt_index=0,
        )
    executor.execute.assert_not_called()


def test_parent_revocation_between_decision_and_effect_denies_new_side_effect() -> None:
    registry = _registry()
    registry.register(
        tenant_id="tenant-agent",
        business_id="business-agent",
        agent_id="root-agent",
        idempotency_key="root-create",
        agent_type="business",
        agent_version="v1",
        capability_scope=("notify_owner",),
        occurred_at_ms=100,
    )
    registry.register(
        tenant_id="tenant-agent",
        business_id="business-agent",
        agent_id="child-agent",
        idempotency_key="child-create",
        agent_type="worker",
        agent_version="v1",
        delegated_by="root-agent",
        capability_scope=("notify_owner",),
        occurred_at_ms=110,
    )

    executor = SimpleNamespace(
        execute=Mock(
            return_value=ExecutionResult(
                ok=True,
                output={"attempted": True, "executed": True, "verified": True},
                decision_id="decision-agent",
                correlation_id="correlation-agent",
            )
        )
    )
    contract = _contract(registry=registry, issuer_id="child-agent", executor=executor)
    request = _request(agent_id="child-agent")
    artifacts = AutonomyDecisionStep(contract=contract).evaluate(
        request=request,
        state={},
        trace=SimpleNamespace(record=Mock()),
        step_index=0,
        attempt_index=0,
    )
    assert artifacts.action_intent.agent_id == "child-agent"

    registry.revoke(
        tenant_id="tenant-agent",
        business_id="business-agent",
        agent_id="root-agent",
        idempotency_key="root-revoke",
        occurred_at_ms=120,
    )

    result = AutonomyExecutionStep(contract=contract).execute(
        request=request,
        executable_action=artifacts.executable_action,
        envelope=artifacts.envelope,
        autonomy_decision=artifacts.autonomy_decision,
    )
    assert result.ok is False
    assert result.output["attempted"] is False
    assert result.output["executed"] is False
    assert result.output["status"] == "agent_authorization_denied"
    executor.execute.assert_not_called()
