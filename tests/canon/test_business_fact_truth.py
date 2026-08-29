import pytest

from contracts.event_store import BUSINESS_FACT_EVENT_TYPE, BusinessFactV1, normalize_append_event
from runtime.platform.event_store.memory_event_store import MemoryEventStore


def _fact(**overrides) -> BusinessFactV1:
    values = {
        "fact_id": "fact-1",
        "tenant_id": "tenant-1",
        "business_id": "business-1",
        "fact_type": "customer.status_changed",
        "entity_id": "customer-1",
        "event_time_ms": 100,
        "observed_at_ms": 200,
        "source": "crm",
        "payload": {"status": "active"},
        "provenance": {"provider": "crm", "record_id": "r-1"},
        "decision_id": "decision-1",
        "correlation_id": "correlation-1",
    }
    values.update(overrides)
    return BusinessFactV1(**values)


def test_business_fact_uses_existing_event_store_and_preserves_truth_metadata() -> None:
    store = MemoryEventStore()
    store.append_event(_fact().as_event())
    [event] = list(store.iter_events(tenant_id="tenant-1", start_ms=0))
    assert event["event_id"] == "fact-1"
    assert event["event_type"] == BUSINESS_FACT_EVENT_TYPE
    assert event["timestamp_ms"] == 200
    assert event["decision_id"] == "decision-1"
    assert event["correlation_id"] == "correlation-1"
    assert event["payload"]["schema_version"] == 1
    assert event["payload"]["event_time_ms"] == 100
    assert event["payload"]["observed_at_ms"] == 200
    assert event["payload"]["payload"] == {"status": "active"}
    assert event["payload"]["provenance"]["record_id"] == "r-1"


def test_business_fact_nested_truth_is_snapshotted() -> None:
    source_payload = {"profile": {"tags": ["active"]}}
    source_provenance = {"origin": {"record_ids": ["r-1"]}}
    fact = _fact(payload=source_payload, provenance=source_provenance)
    store = MemoryEventStore()
    store.append_event(fact.as_event())
    source_payload["profile"]["tags"].append("mutated")
    source_provenance["origin"]["record_ids"].append("r-2")
    [event] = list(store.iter_events(tenant_id="tenant-1", start_ms=0))
    assert fact.payload == {"profile": {"tags": ["active"]}}
    assert fact.provenance == {"origin": {"record_ids": ["r-1"]}}
    assert event["payload"]["payload"] == {"profile": {"tags": ["active"]}}
    assert event["payload"]["provenance"] == {"origin": {"record_ids": ["r-1"]}}


def test_business_fact_correction_is_append_only() -> None:
    store = MemoryEventStore()
    store.append_event(_fact().as_event())
    store.append_event(_fact(fact_id="fact-2", observed_at_ms=300, payload={"status": "inactive"}, supersedes_fact_id="fact-1").as_event())
    events = list(store.iter_events(tenant_id="tenant-1", start_ms=0))
    assert [event["event_id"] for event in events] == ["fact-1", "fact-2"]
    assert events[1]["payload"]["supersedes_fact_id"] == "fact-1"


def test_explicit_zero_timestamp_is_preserved_by_append_normalization() -> None:
    normalized = normalize_append_event(_fact(observed_at_ms=0).as_event())
    assert normalized.timestamp_ms == 0
    assert normalized.payload["observed_at_ms"] == 0


@pytest.mark.parametrize("field", ["fact_id", "tenant_id", "business_id", "fact_type", "entity_id", "source"])
def test_business_fact_identity_fails_closed(field: str) -> None:
    values = _fact().__dict__.copy()
    values[field] = ""
    with pytest.raises(ValueError, match="identity and source fields are required"):
        BusinessFactV1(**values)
