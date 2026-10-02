from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from application.outcome.evidence_projection import (
    OUTCOME_OBSERVED_EVENT_TYPE,
    BusinessOutcomeEventProjectionConflict,
    BusinessOutcomeEventSpineProjector,
)
from attribution.attribution_engine import AttributionEngine
from contracts.action_intent import ActionIntentV1
from contracts.business_outcome import BusinessOutcomeV1
from contracts.event_store import canonical_business_event_contract
from runtime.platform.event_store.memory_event_store import MemoryEventStore
from storage.evidence_store import EvidenceRecord


def _record() -> EvidenceRecord:
    intent = ActionIntentV1.from_projection(
        intent_id="intent:decision-event",
        tenant_id="tenant-1",
        business_id="biz-1",
        decision_id="decision-event",
        correlation_id="correlation-event",
        action_type="send_email",
        channel="email",
        payload={},
        payload_hash="0" * 64,
        evidence_refs=("world-evidence-1",),
        derived_fact_ref="semantic-state-1",
    )
    outcome = BusinessOutcomeV1.from_feedback(
        tenant_id="tenant-1",
        business_id="biz-1",
        run_id="run-event",
        intent_id=intent.intent_id,
        decision_id=intent.decision_id,
        action_id="action-event",
        action_type="send_email",
        goal="Grow revenue",
        status="verified",
        feedback={
            "attempted": True,
            "executed": True,
            "verified": True,
            "verification_status": "verified",
            "goal_evaluation": {
                "achieved": False,
                "terminal": False,
                "completion_ratio": 0.4,
                "success_confidence": 0.8,
            },
            "execution_feedback": {"source_of_truth": "provider_receipt"},
            "external_refs": ["provider:message:1"],
            "evidence_status": "verified",
        },
        evidence_refs=("world-evidence-1",),
        derived_fact_ref="semantic-state-1",
    )
    return EvidenceRecord(
        evidence_id="evidence-event-1",
        tenant_id="tenant-1",
        scope="closed_loop",
        run_id="run-event",
        action_id="action-event",
        action_type="send_email",
        verification_status="verified",
        created_at=datetime(2026, 9, 19, 8, 0, tzinfo=UTC),
        source="provider_receipt",
        source_type="closed_loop_verification",
        business_id="biz-1",
        privacy_class="internal",
        retention_policy="closed_loop_evidence",
        lineage={
            "source": "provider:message:1",
            "normalization": "persistence-key-1",
            "derived_fact": "semantic-state-1",
            "decision": "decision-event",
            "action": "action-event",
            "outcome": "outcome:action-event",
        },
        refs=("world-evidence-1", "provider:message:1"),
        labels={"goal_id": "goal-event"},
        payload={
            "action_intent": intent.as_dict(),
            "business_outcome": outcome.as_dict(),
        },
    ).normalized()


def test_outcome_projection_is_idempotent_and_carries_canonical_lineage() -> None:
    store = MemoryEventStore()
    projector = BusinessOutcomeEventSpineProjector(store)
    record = _record()

    first = projector.project(record)
    second = projector.project(record)

    assert first == second == "closed-loop-outcome:evidence-event-1"
    events = list(
        store.iter_events(
            tenant_id="tenant-1",
            start_ms=0,
            event_type=OUTCOME_OBSERVED_EVENT_TYPE,
        )
    )
    assert len(events) == 1
    assert events[0]["decision_id"] == "decision-event"
    contract = canonical_business_event_contract(events[0])
    assert contract["schema_version"] == 2
    assert contract["business_id"] == "biz-1"
    assert contract["correlation_id"] == "correlation-event"
    assert contract["causation_id"] == "intent:decision-event"
    assert contract["evidence_ids"] == ("evidence-event-1",)
    assert contract["payload"]["goal_id"] == "goal-event"
    assert contract["payload"]["outcome"]["outcome_id"] == "outcome:action-event"


def test_outcome_projection_rejects_conflicting_existing_event() -> None:
    store = MemoryEventStore()
    projector = BusinessOutcomeEventSpineProjector(store)
    record = _record()
    event_id = projector.project(record)
    assert event_id is not None

    store[0]["payload"]["outcome"]["status"] = "forged"
    with pytest.raises(
        BusinessOutcomeEventProjectionConflict,
        match="conflicts with canonical evidence",
    ):
        projector.project(record)


def test_legacy_partial_outcome_is_not_promoted_to_canonical_event() -> None:
    record = _record()
    legacy = EvidenceRecord(
        **{
            **record.__dict__,
            "payload": {
                "business_outcome": {
                    "outcome_id": "outcome:action-event",
                    "source_of_truth": "provider_receipt",
                }
            },
        }
    ).normalized()
    store = MemoryEventStore()

    assert BusinessOutcomeEventSpineProjector(store).project(legacy) is None
    assert list(store.iter_events(tenant_id="tenant-1", start_ms=0)) == []



def test_outcome_projection_preserves_legacy_payload_shape_without_goal() -> None:
    record = _record()
    legacy_shape = EvidenceRecord(
        **{
            **record.__dict__,
            "labels": {},
        }
    ).normalized()
    store = MemoryEventStore()
    projector = BusinessOutcomeEventSpineProjector(store)

    event_id = projector.project(legacy_shape)
    events = [
        dict(row)
        for row in store.iter_events(
            tenant_id=legacy_shape.tenant_id,
            start_ms=0,
            event_type=OUTCOME_OBSERVED_EVENT_TYPE,
        )
        if str(row.get("event_id") or "") == str(event_id)
    ]
    assert len(events) == 1
    assert "goal_id" not in events[0]["payload"]


def test_outcome_projection_rejects_tampered_canonical_attribution_lineage() -> None:
    record = _record()
    attribution = AttributionEngine().attribute_canonical(
        {
            "tenant_id": record.tenant_id,
            "business_id": record.business_id,
            "goal_id": "goal-event",
            "decision_id": "decision-event",
            "action_id": "action-event",
            "interaction_id": "interaction-1",
            "customer_id": "customer-1",
            "conversion_id": "conversion-1",
            "payment_id": "payment-1",
            "outcome_id": "outcome:action-event",
            "verified": True,
            "attribution_verified": True,
            "evidence_refs": ("world-evidence-1",),
        }
    )
    payload = dict(record.payload)
    outcome_body = dict(payload["business_outcome"])
    outcome_body["metrics"] = {
        "interaction_id": "interaction-1",
        "customer_id": "customer-1",
        "conversion_id": "conversion-1",
        "payment_id": "payment-1",
    }
    payload["business_outcome"] = outcome_body
    tampered = dict(attribution)
    tampered_payload = dict(tampered["payload"])
    tampered_chain = dict(tampered_payload["chain"])
    tampered_chain["payment"] = "payment-forged"
    tampered_payload["chain"] = tampered_chain
    tampered["payload"] = tampered_payload
    payload["attribution"] = tampered
    with pytest.raises(BusinessOutcomeEventProjectionConflict, match="lineage conflicts"):
        BusinessOutcomeEventSpineProjector(MemoryEventStore()).project(
            replace(record, payload=payload)
        )


def test_outcome_projection_replays_pre_phase13_event_without_rewriting_it() -> None:
    store = MemoryEventStore()
    projector = BusinessOutcomeEventSpineProjector(store)
    record = _record()
    event_id = projector.project(record)
    assert event_id is not None

    legacy_payload = dict(store[0]["payload"])
    legacy_payload.pop("outcome_taxonomy", None)
    legacy_payload.pop("attribution", None)
    legacy_payload["schema_version"] = 1
    store[0]["payload"] = legacy_payload
    legacy_snapshot = dict(store[0])
    legacy_snapshot["payload"] = dict(legacy_payload)

    assert projector.project(record) == event_id
    assert len(store) == 1
    assert dict(store[0]) == legacy_snapshot
    assert "outcome_taxonomy" not in store[0]["payload"]
    assert "attribution" not in store[0]["payload"]
    assert store[0]["payload"]["schema_version"] == 1

    store[0]["payload"]["schema_version"] = 2
    with pytest.raises(
        BusinessOutcomeEventProjectionConflict,
        match="conflicts with canonical evidence",
    ):
        projector.project(record)
    store[0]["payload"]["schema_version"] = 1

    store[0]["payload"]["outcome"]["status"] = "forged"
    with pytest.raises(
        BusinessOutcomeEventProjectionConflict,
        match="conflicts with canonical evidence",
    ):
        projector.project(record)

