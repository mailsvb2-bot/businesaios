import pytest

from application.ontology import EventFactLifecycleWriter
from contracts.event_store import canonical_business_event_contract
from reliability import InMemoryIdempotencyStore
from runtime.platform.event_store.memory_event_store import MemoryEventStore


def _writer() -> tuple[EventFactLifecycleWriter, MemoryEventStore]:
    events = MemoryEventStore()
    writer = EventFactLifecycleWriter( event_store=events, idempotency_store=InMemoryIdempotencyStore(), namespace="phase4_contract_test", source="phase4_contract_test", id_prefix="phase4", )
    return writer, events


def test_ontology_writer_propagates_canonical_event_metadata() -> None:
    writer, events = _writer()
    fact_id = writer.append_once( tenant_id="tenant-1", business_id="business-1", entity_id="lead-1", operation="update", idempotency_key="request-1", fact_type="lead.updated", payload={"status": "qualified"}, occurred_at_ms=100, event_metadata={ "actor_id": "owner-1", "agent_id": "agent-1", "decision_id": "decision-1", "correlation_id": "correlation-1", "causation_id": "cause-1", "recorded_at_ms": 125, "evidence_ids": ("evidence-1", "evidence-2", "evidence-1"), }, )
    [persisted] = list(events.iter_events(tenant_id="tenant-1", start_ms=0))
    assert persisted["event_id"] == fact_id
    assert canonical_business_event_contract(persisted) == { "event_id": fact_id, "event_type": "lead.updated", "schema_version": 1, "business_id": "business-1", "actor_id": "owner-1", "agent_id": "agent-1", "occurred_at": 100, "recorded_at": 125, "correlation_id": "correlation-1", "causation_id": "cause-1", "source": "phase4_contract_test", "payload": {"status": "qualified"}, "evidence_ids": ("evidence-1", "evidence-2"), }
    assert persisted["decision_id"] == "decision-1"


def test_ontology_writer_replay_fails_closed_on_metadata_change() -> None:
    writer, _ = _writer()
    common = { "tenant_id": "tenant-1", "business_id": "business-1", "entity_id": "lead-1", "operation": "update", "idempotency_key": "request-1", "fact_type": "lead.updated", "payload": {"status": "qualified"}, "occurred_at_ms": 100, }
    writer.append_once(**common, event_metadata={"actor_id": "owner-1"})
    with pytest.raises(ValueError, match="event metadata"):
        writer.append_once(**common, event_metadata={"actor_id": "owner-2"})


def test_ontology_transition_replay_preserves_metadata_and_rejects_change() -> None:
    writer, events = _writer()
    common = { "tenant_id": "tenant-1", "business_id": "business-1", "entity_id": "lead-1", "expected_state_token": "new:v1", "operation": "qualify", "idempotency_key": "request-transition-1", "fact_type": "lead.qualified", "payload": {"status": "qualified"}, "occurred_at_ms": 200, }
    metadata = { "actor_id": "owner-1", "decision_id": "decision-2", "correlation_id": "correlation-2", "causation_id": "cause-2", "recorded_at_ms": 225, "evidence_ids": ("evidence-3",), }
    fact_id = writer.append_transition_once(**common, event_metadata=metadata)
    assert writer.append_transition_once(**common, event_metadata=metadata) == fact_id
    [persisted] = list(events.iter_events(tenant_id="tenant-1", start_ms=0))
    assert persisted["event_id"] == fact_id
    assert persisted["decision_id"] == "decision-2"
    assert canonical_business_event_contract(persisted)["evidence_ids"] == ("evidence-3",)
    with pytest.raises(ValueError, match="event metadata"):
        writer.append_transition_once( **common, event_metadata={**metadata, "actor_id": "owner-2"}, )


def test_ontology_writer_rejects_unknown_event_metadata() -> None:
    writer, _ = _writer()
    with pytest.raises(ValueError, match="unsupported canonical event metadata"):
        writer.append_once( tenant_id="tenant-1", business_id="business-1", entity_id="lead-1", operation="update", idempotency_key="request-1", fact_type="lead.updated", payload={"status": "qualified"}, occurred_at_ms=100, event_metadata={"provider_secret": "must-not-enter-event-contract"}, )


def test_ontology_writer_can_find_existing_fact_by_key_after_state_advance() -> None:
    writer, events = _writer()
    metadata = {"actor_id": "owner-1", "decision_id": "decision-transition"}
    fact_id = writer.append_once( tenant_id="tenant-1", business_id="business-1", entity_id="invoice-1", operation="record_payment", idempotency_key="payment-request-1", fact_type="invoice.payment_recorded", payload={"paid_minor": 400, "status": "partially_paid"}, occurred_at_ms=300, event_metadata=metadata, )
    found = writer.find_existing_for_key( tenant_id="tenant-1", business_id="business-1", entity_id="invoice-1", operation="record_payment", idempotency_key="payment-request-1", fact_type="invoice.payment_recorded", event_metadata=metadata, )
    assert found is not None
    assert found["event_id"] == fact_id
    assert len(list(events.iter_events(tenant_id="tenant-1", start_ms=0))) == 1
    with pytest.raises(ValueError, match="event metadata"):
        writer.find_existing_for_key( tenant_id="tenant-1", business_id="business-1", entity_id="invoice-1", operation="record_payment", idempotency_key="payment-request-1", fact_type="invoice.payment_recorded", event_metadata={**metadata, "actor_id": "owner-2"}, )


def test_schema_v2_payment_event_uses_the_same_canonical_event_contract() -> None:
    payment_payload = {
        "schema_version": 2,
        "external_id": "payment-1",
        "status": "pending",
        "provider": "yookassa",
        "amount": 1500,
        "currency": "RUB",
        "metadata": {
            "tenant_id": "tenant-1",
            "business_id": "business-1",
            "product_id": "product-1",
            "order_id": "order-1",
        },
    }
    event = {
        "event_id": "payment-event-1",
        "tenant_id": "tenant-1",
        "user_id": "customer-1",
        "source": "payments",
        "event_type": "payment_created",
        "timestamp_ms": 500,
        "decision_id": "decision-payment-1",
        "correlation_id": "correlation-payment-1",
        "payload": payment_payload,
    }

    assert canonical_business_event_contract(event) == {
        "event_id": "payment-event-1",
        "event_type": "payment_created",
        "schema_version": 2,
        "business_id": "business-1",
        "actor_id": None,
        "agent_id": None,
        "occurred_at": 500,
        "recorded_at": 500,
        "correlation_id": "correlation-payment-1",
        "causation_id": None,
        "source": "payments",
        "payload": payment_payload,
        "evidence_ids": (),
    }


def test_native_business_event_fails_closed_without_versioned_business_scope() -> None:
    event = {
        "event_id": "legacy-payment-event",
        "tenant_id": "tenant-1",
        "source": "payments",
        "event_type": "payment_created",
        "timestamp_ms": 600,
        "payload": {"metadata": {"tenant_id": "tenant-1"}},
    }
    with pytest.raises(ValueError, match="schema_version"):
        canonical_business_event_contract(event)

    event["payload"] = {"schema_version": 2, "metadata": {"tenant_id": "tenant-1"}}
    with pytest.raises(ValueError, match="business_id"):
        canonical_business_event_contract(event)
