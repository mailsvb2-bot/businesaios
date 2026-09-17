import pytest

from application.ontology import EventFactLifecycleWriter
from contracts.event_store import canonical_business_event_contract
from reliability import InMemoryIdempotencyStore
from runtime.platform.event_store.memory_event_store import MemoryEventStore


def _writer() -> tuple[EventFactLifecycleWriter, MemoryEventStore]:
    events = MemoryEventStore()
    writer = EventFactLifecycleWriter(
        event_store=events,
        idempotency_store=InMemoryIdempotencyStore(),
        namespace="phase4_contract_test",
        source="phase4_contract_test",
        id_prefix="phase4",
    )
    return writer, events


def test_ontology_writer_propagates_canonical_event_metadata() -> None:
    writer, events = _writer()
    fact_id = writer.append_once(
        tenant_id="tenant-1",
        business_id="business-1",
        entity_id="lead-1",
        operation="update",
        idempotency_key="request-1",
        fact_type="lead.updated",
        payload={"status": "qualified"},
        occurred_at_ms=100,
        event_metadata={
            "actor_id": "owner-1",
            "agent_id": "agent-1",
            "decision_id": "decision-1",
            "correlation_id": "correlation-1",
            "causation_id": "cause-1",
            "recorded_at_ms": 125,
            "evidence_ids": ("evidence-1", "evidence-2", "evidence-1"),
        },
    )

    [persisted] = list(events.iter_events(tenant_id="tenant-1", start_ms=0))
    assert persisted["event_id"] == fact_id
    assert canonical_business_event_contract(persisted) == {
        "event_id": fact_id,
        "event_type": "lead.updated",
        "schema_version": 1,
        "business_id": "business-1",
        "actor_id": "owner-1",
        "agent_id": "agent-1",
        "occurred_at": 100,
        "recorded_at": 125,
        "correlation_id": "correlation-1",
        "causation_id": "cause-1",
        "source": "phase4_contract_test",
        "payload": {"status": "qualified"},
        "evidence_ids": ("evidence-1", "evidence-2"),
    }
    assert persisted["decision_id"] == "decision-1"


def test_ontology_writer_replay_fails_closed_on_metadata_change() -> None:
    writer, _ = _writer()
    common = {
        "tenant_id": "tenant-1",
        "business_id": "business-1",
        "entity_id": "lead-1",
        "operation": "update",
        "idempotency_key": "request-1",
        "fact_type": "lead.updated",
        "payload": {"status": "qualified"},
        "occurred_at_ms": 100,
    }
    writer.append_once(**common, event_metadata={"actor_id": "owner-1"})

    with pytest.raises(ValueError, match="event metadata"):
        writer.append_once(**common, event_metadata={"actor_id": "owner-2"})


def test_ontology_writer_rejects_unknown_event_metadata() -> None:
    writer, _ = _writer()
    with pytest.raises(ValueError, match="unsupported canonical event metadata"):
        writer.append_once(
            tenant_id="tenant-1",
            business_id="business-1",
            entity_id="lead-1",
            operation="update",
            idempotency_key="request-1",
            fact_type="lead.updated",
            payload={"status": "qualified"},
            occurred_at_ms=100,
            event_metadata={"provider_secret": "must-not-enter-event-contract"},
        )
