from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from application.decision_runtime.emission import (
    DecisionEventProjectionConflict,
    project_decision_proposed_event,
)
from contracts.action_intent import ActionIntentV1
from contracts.event_store import canonical_business_event_contract
from core.events.event_types import DECISION_PROPOSED
from runtime.platform.event_store.memory_event_store import MemoryEventStore


@dataclass(frozen=True)
class _Decision:
    decision_id: str = "decision-1"
    issuer_id: str = "sovereign-decision"
    issued_at_ms: int = 1234
    expires_at_ms: int = 2234
    policy_id: str = "strategy-policy-1"
    action: str = "send_message"
    payload: dict[str, Any] = field(default_factory=dict)
    snapshot_id: str = "snapshot-1"
    state_hash: str = "state-hash-1"
    correlation_id: str = "correlation-1"
    state_schema_version: int = 1
    action_schema_version: int = 1
    envelope_version: int = 1


@dataclass(frozen=True)
class _Envelope:
    decision: _Decision = field(default_factory=_Decision)
    payload_hash: str = "a" * 64


def _intent(**patch: Any) -> ActionIntentV1:
    payload = {"actor_id": "owner-1", "recipient": "must-not-enter-decision-event"}
    values = {
        "intent_id": "intent:decision-1",
        "tenant_id": "tenant-1",
        "business_id": "business-1",
        "decision_id": "decision-1",
        "correlation_id": "correlation-1",
        "action_type": "send_message",
        "channel": "max",
        "payload": payload,
        "payload_hash": "b" * 64,
        "evidence_refs": ("evidence-1", "evidence-1", "evidence-2"),
        "derived_fact_ref": "semantic-state-1",
    }
    values.update(patch)
    return ActionIntentV1.from_projection(**values)


def test_decision_proposed_is_canonical_idempotent_and_pii_minimal() -> None:
    store = MemoryEventStore()
    envelope = _Envelope()
    intent = _intent()

    first = project_decision_proposed_event(event_store=store, envelope=envelope, action_intent=intent)
    second = project_decision_proposed_event(event_store=store, envelope=envelope, action_intent=intent)

    assert first == second
    rows = list(store.iter_events(tenant_id="tenant-1", start_ms=0, event_type=DECISION_PROPOSED))
    assert len(rows) == 1
    canonical = canonical_business_event_contract(rows[0])
    assert canonical["business_id"] == "business-1"
    assert canonical["actor_id"] == "owner-1"
    assert canonical["agent_id"] == "sovereign-decision"
    assert canonical["occurred_at"] == 1234
    assert canonical["recorded_at"] == 1234
    assert canonical["correlation_id"] == "correlation-1"
    assert canonical["causation_id"] == "semantic-state-1"
    assert canonical["evidence_ids"] == ("evidence-1", "evidence-2")
    assert canonical["payload"]["decision"] == {
        "decision_id": "decision-1",
        "action_type": "send_message",
        "policy_id": "strategy-policy-1",
        "snapshot_id": "snapshot-1",
        "state_hash": "state-hash-1",
        "decision_payload_hash": "a" * 64,
        "action_intent_id": "intent:decision-1",
        "objective_name": "profit_adjusted_growth",
    }
    assert "recipient" not in canonical["payload"]


def test_decision_proposed_fails_closed_without_canonical_event_store() -> None:
    with pytest.raises(RuntimeError, match="DECISION_EVENT_STORE_REQUIRED"):
        project_decision_proposed_event(event_store=None, envelope=_Envelope(), action_intent=_intent())


def test_decision_proposed_rejects_action_intent_identity_drift() -> None:
    with pytest.raises(DecisionEventProjectionConflict, match="ActionIntent decision identity mismatch"):
        project_decision_proposed_event(
            event_store=MemoryEventStore(),
            envelope=_Envelope(),
            action_intent=_intent(decision_id="decision-other"),
        )


def test_decision_proposed_rejects_conflicting_durable_row() -> None:
    store = MemoryEventStore()
    envelope = _Envelope()
    intent = _intent()
    project_decision_proposed_event(event_store=store, envelope=envelope, action_intent=intent)
    store[0]["payload"]["decision"]["action_type"] = "forged"

    with pytest.raises(DecisionEventProjectionConflict, match="conflicts with canonical Decision lineage"):
        project_decision_proposed_event(event_store=store, envelope=envelope, action_intent=intent)


def test_autonomy_projects_decision_before_policy_transition() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "application/autonomy/autonomy_decision_step.py").read_text(encoding="utf-8")
    intent = source.index("action_intent = self._project_action_intent")
    projection = source.index("self._project_decision_event(", intent)
    policy = source.index("autonomy_decision = evaluate_autonomy_transition", projection)
    assert intent < projection < policy
