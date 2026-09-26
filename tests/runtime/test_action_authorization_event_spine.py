from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from contracts.event_store import canonical_business_event_contract
from core.events.event_types import ACTION_AMBIGUOUS, ACTION_AUTHORIZED, ACTION_EXECUTED, ACTION_FAILED
from core.ai.schema_registry import DecisionSchema
from runtime.execution.executor_audit import (
    ActionAuthorizationEventProjectionConflict,
    ActionEventProjectionConflict,
    project_action_ambiguous_event,
    project_action_authorized_event,
    project_action_executed_event,
    project_action_failed_event,
)
from runtime.platform.event_store.memory_event_store import MemoryEventStore


@dataclass(frozen=True)
class _Decision:
    decision_id: str = "decision-1"
    correlation_id: str = "correlation-1"
    action: str = "send_message"
    issued_at_ms: int = 1234
    issuer_id: str = "sovereign-decision"
    payload: dict[str, Any] = field(
        default_factory=lambda: {
            "tenant_id": "tenant-1",
            "business_id": "business-1",
            "intent_id": "intent:decision-1",
            "action_id": "action:decision-1",
            "action_channel": "max",
            "evidence_refs": ["evidence-1", "evidence-1", "evidence-2"],
            "derived_fact_ref": "semantic-state-1",
            "capability_planning": {"allowed": True},
            "autonomy_safety": {"allowed": True, "operator_required": False, "reason": "within_bounds"},
            "policy_decision": {
                "schema_version": 1,
                "intent_id": "intent:decision-1",
                "decision_id": "decision-1",
                "tenant_id": "tenant-1",
                "business_id": "business-1",
                "tier": "bounded_autonomy",
                "action_type": "send_message",
                "action_class": "communications_write",
                "verdict": "allowed",
                "allowed": True,
                "approval_required": False,
                "blocked_by_policy": False,
                "handoff_reason": None,
            },
        }
    )


class _AppendThenRaiseStore(MemoryEventStore):
    def __init__(self) -> None:
        super().__init__()
        self.fail_once = True

    def append_event(self, event: dict):
        super().append_event(event)
        if self.fail_once:
            self.fail_once = False
            raise RuntimeError("commit_ack_lost")


def test_action_authorized_is_canonical_business_event_and_retry_is_idempotent() -> None:
    store = MemoryEventStore()
    decision = _Decision()

    first = project_action_authorized_event(event_store=store, decision=decision)
    second = project_action_authorized_event(event_store=store, decision=decision)

    assert first == second
    rows = list(store.iter_events(tenant_id="tenant-1", start_ms=0, event_type=ACTION_AUTHORIZED))
    assert len(rows) == 1
    canonical = canonical_business_event_contract(rows[0])
    assert canonical["event_type"] == ACTION_AUTHORIZED
    assert canonical["business_id"] == "business-1"
    assert canonical["occurred_at"] == 1234
    assert canonical["recorded_at"] == 1234
    assert canonical["causation_id"] == "intent:decision-1"
    assert canonical["evidence_ids"] == ("evidence-1", "evidence-2")
    assert canonical["payload"]["action"] == {
        "intent_id": "intent:decision-1",
        "action_id": "action:decision-1",
        "action_type": "send_message",
        "channel": "max",
        "derived_fact_ref": "semantic-state-1",
    }
    assert "recipient" not in canonical["payload"]
    assert "goal_id" not in canonical["payload"]


def test_action_authorized_repairs_append_ack_loss_without_duplicate() -> None:
    store = _AppendThenRaiseStore()
    event_id = project_action_authorized_event(event_store=store, decision=_Decision())
    rows = list(store.iter_events(tenant_id="tenant-1", start_ms=0, event_type=ACTION_AUTHORIZED))
    assert event_id
    assert len(rows) == 1


def test_action_intent_path_fails_closed_without_canonical_event_store() -> None:
    with pytest.raises(RuntimeError, match="ACTION_AUTHORIZATION_EVENT_STORE_REQUIRED"):
        project_action_authorized_event(event_store=None, decision=_Decision())


def test_policy_identity_mismatch_is_rejected_before_append() -> None:
    store = MemoryEventStore()
    decision = _Decision()
    payload = dict(decision.payload)
    policy = dict(payload["policy_decision"])
    policy["business_id"] = "business-other"
    payload["policy_decision"] = policy
    forged = _Decision(payload=payload)

    with pytest.raises(ActionAuthorizationEventProjectionConflict, match="policy business identity mismatch"):
        project_action_authorized_event(event_store=store, decision=forged)
    assert list(store.iter_events(tenant_id="tenant-1", start_ms=0, event_type=ACTION_AUTHORIZED)) == []


@pytest.mark.parametrize(
    "patch, message",
    [
        ({"autonomy_safety": {"allowed": False, "operator_required": True}}, "successful runtime safety preflight"),
        ({"capability_planning": {"allowed": False}}, "disabled capability"),
        (
            {
                "policy_decision": {
                    "schema_version": 1,
                    "intent_id": "intent:decision-1",
                    "decision_id": "decision-1",
                    "tenant_id": "tenant-1",
                    "business_id": "business-1",
                    "tier": "bounded_autonomy",
                    "action_type": "send_message",
                    "action_class": "communications_write",
                    "verdict": "approval_required",
                    "allowed": False,
                    "approval_required": True,
                    "blocked_by_policy": False,
                    "handoff_reason": "operator",
                }
            },
            "allowed PolicyDecisionV1",
        ),
    ],
)
def test_restricted_action_cannot_be_recorded_as_authorized(patch: dict[str, Any], message: str) -> None:
    store = MemoryEventStore()
    decision = _Decision()
    payload = dict(decision.payload)
    payload.update(patch)

    with pytest.raises(ActionAuthorizationEventProjectionConflict, match=message):
        project_action_authorized_event(event_store=store, decision=_Decision(payload=payload))


def test_executor_projects_authorization_after_governance_and_before_execute_once() -> None:
    root = Path(__file__).resolve().parents[2]
    stages = (root / "runtime/execution/executor_stages.py").read_text(encoding="utf-8")
    governance = stages.index("review_governance_execution(executor=executor, env=env)")
    projection = stages.index("project_action_authorized_event(")
    execute_once = stages.index("executor._guard.execute_once(env)")
    assert governance < projection < execute_once


def test_headless_resigned_execution_envelope_carries_canonical_intent_and_policy_lineage() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "application/autonomy/autonomy_execution_step.py").read_text(encoding="utf-8")
    for marker in (
        'final_payload["intent_id"]',
        'final_payload["action_id"]',
        'final_payload["evidence_refs"]',
        'final_payload["derived_fact_ref"]',
        'final_payload["policy_decision"]',
    ):
        assert marker in source


def test_decision_schema_allows_only_declared_action_lineage_metadata() -> None:
    schema = DecisionSchema(
        required={"text"},
        optional=set(),
        field_types={"text": str},
        allow_additional=False,
    )
    schema.validate(
        {
            "text": "hello",
            "intent_id": "intent:decision-1",
            "action_id": "action:decision-1",
            "action_channel": "max",
            "evidence_refs": ["evidence-1"],
            "derived_fact_ref": "semantic-state-1",
            "policy_decision": {"schema_version": 1, "verdict": "allowed"},
        }
    )
    with pytest.raises(ValueError, match="UNKNOWN_PAYLOAD_KEYS"):
        schema.validate({"text": "hello", "unexpected_execution_metadata": True})


def test_action_executed_requires_authorization_and_is_idempotent() -> None:
    store = MemoryEventStore()
    decision = _Decision()
    authorization_id = project_action_authorized_event(event_store=store, decision=decision)

    first = project_action_executed_event(
        event_store=store,
        decision=decision,
        verification={"verified": True, "status": "verified", "external_refs": ["provider-receipt"]},
        output={"status": "delivered", "provider_payload": "must-not-leak"},
    )
    second = project_action_executed_event(
        event_store=store,
        decision=decision,
        verification={"verified": True, "status": "verified", "external_refs": ["provider-receipt"]},
        output={"status": "delivered", "provider_payload": "different-retry-payload"},
    )

    assert first == second
    rows = list(store.iter_events(tenant_id="tenant-1", start_ms=0, event_type=ACTION_EXECUTED))
    assert len(rows) == 1
    canonical = canonical_business_event_contract(rows[0])
    assert canonical["causation_id"] == authorization_id
    assert canonical["payload"]["lifecycle"] == {
        "status": "executed",
        "handler_status": "delivered",
        "verification_status": "verified",
        "external_ref_count": 1,
    }
    assert "provider_payload" not in canonical["payload"]


def test_action_failed_requires_authorization_and_is_idempotent() -> None:
    store = MemoryEventStore()
    decision = _Decision()
    authorization_id = project_action_authorized_event(event_store=store, decision=decision)

    first = project_action_failed_event(
        event_store=store,
        decision=decision,
        reason="verification_failed",
        error_type="ExecutionContractLockError",
    )
    second = project_action_failed_event(
        event_store=store,
        decision=decision,
        reason="verification_failed",
        error_type="ExecutionContractLockError",
    )

    assert first == second
    rows = list(store.iter_events(tenant_id="tenant-1", start_ms=0, event_type=ACTION_FAILED))
    assert len(rows) == 1
    canonical = canonical_business_event_contract(rows[0])
    assert canonical["causation_id"] == authorization_id
    assert canonical["payload"]["lifecycle"]["status"] == "failed"
    assert canonical["payload"]["lifecycle"]["reason"] == "verification_failed"


def test_terminal_action_event_without_authorization_fails_closed() -> None:
    store = MemoryEventStore()
    with pytest.raises(ActionEventProjectionConflict, match="durable action.authorized predecessor"):
        project_action_executed_event(
            event_store=store,
            decision=_Decision(),
            verification={"verified": True, "status": "verified"},
            output={"status": "delivered"},
        )


def test_action_ambiguous_requires_authorization_and_is_idempotent() -> None:
    store = MemoryEventStore()
    decision = _Decision()
    authorization_id = project_action_authorized_event(event_store=store, decision=decision)

    first = project_action_ambiguous_event(
        event_store=store,
        decision=decision,
        reason="verification_outcome_unknown",
        error_type="TimeoutError",
    )
    second = project_action_ambiguous_event(
        event_store=store,
        decision=decision,
        reason="verification_outcome_unknown",
        error_type="TimeoutError",
    )

    assert first == second
    rows = list(store.iter_events(tenant_id="tenant-1", start_ms=0, event_type=ACTION_AMBIGUOUS))
    assert len(rows) == 1
    canonical = canonical_business_event_contract(rows[0])
    assert canonical["causation_id"] == authorization_id
    assert canonical["payload"]["lifecycle"] == {
        "status": "ambiguous",
        "reason": "verification_outcome_unknown",
        "error_type": "TimeoutError",
        "recovery": "reconcile_before_retry",
    }


def test_action_executed_requires_explicit_successful_verification() -> None:
    store = MemoryEventStore()
    decision = _Decision()
    project_action_authorized_event(event_store=store, decision=decision)

    with pytest.raises(ActionEventProjectionConflict, match="explicit successful verification"):
        project_action_executed_event(
            event_store=store,
            decision=decision,
            verification={"status": "unknown"},
            output={"status": "delivered"},
        )
    assert list(store.iter_events(tenant_id="tenant-1", start_ms=0, event_type=ACTION_EXECUTED)) == []


def test_executor_projects_terminal_action_chronology_at_verified_boundaries() -> None:
    root = Path(__file__).resolve().parents[2]
    stages = (root / "runtime/execution/executor_stages.py").read_text(encoding="utf-8")
    dispatch = stages.index("executor._handlers.dispatch")
    dispatch_ambiguous = stages.index('reason="dispatch_outcome_unknown"', dispatch)
    effect_failed = stages.index('reason="effect_failed"', dispatch_ambiguous)
    verification = stages.index("verification_result = verify_execution_contract", effect_failed)
    verification_ambiguous = stages.index('reason="verification_outcome_unknown"', verification)
    executed_projection = stages.index("project_action_executed_event(", verification_ambiguous)
    outcome_commit = stages.index("committed_output = commit_verified_execution", executed_projection)
    assert dispatch < dispatch_ambiguous < effect_failed < verification
    assert verification < verification_ambiguous < executed_projection < outcome_commit



def test_goal_bound_action_events_preserve_goal_identity_without_changing_legacy_shape() -> None:
    store = MemoryEventStore()
    base = _Decision()
    payload = dict(base.payload)
    payload["goal_id"] = "goal-1"
    decision = _Decision(payload=payload)

    project_action_authorized_event(event_store=store, decision=decision)
    project_action_executed_event(
        event_store=store,
        decision=decision,
        verification={
            "verified": True,
            "status": "verified",
            "external_refs": ["provider-receipt"],
        },
        output={"status": "delivered"},
    )

    authorized = list(
        store.iter_events(
            tenant_id="tenant-1",
            start_ms=0,
            event_type=ACTION_AUTHORIZED,
        )
    )
    executed = list(
        store.iter_events(
            tenant_id="tenant-1",
            start_ms=0,
            event_type=ACTION_EXECUTED,
        )
    )
    assert len(authorized) == 1
    assert len(executed) == 1
    assert authorized[0]["payload"]["goal_id"] == "goal-1"
    assert executed[0]["payload"]["goal_id"] == "goal-1"
