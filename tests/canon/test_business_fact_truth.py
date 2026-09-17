import pytest

from contracts.event_store import (
    BUSINESS_FACT_EVENT_TYPE,
    BusinessFactV1,
    canonical_business_event_contract,
    normalize_append_event,
)
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


def test_canonical_business_event_contract_survives_durable_replay(tmp_path) -> None:
    from runtime.platform.event_store.sqlite_event_store import SqliteEventStore

    path = tmp_path / "events.sqlite3"
    fact = _fact(
        actor_id="owner-1",
        agent_id="agent-1",
        causation_id="cause-1",
        recorded_at_ms=250,
        evidence_ids=("evidence-1", "evidence-2", "evidence-1"),
    )
    with SqliteEventStore(str(path)) as store:
        store.append_event(fact.as_event())
    with SqliteEventStore(str(path)) as store:
        [persisted] = list(store.iter_events(tenant_id="tenant-1", start_ms=0))

    contract = canonical_business_event_contract(persisted)
    assert contract == {
        "event_id": "fact-1",
        "event_type": "customer.status_changed",
        "schema_version": 1,
        "business_id": "business-1",
        "actor_id": "owner-1",
        "agent_id": "agent-1",
        "occurred_at": 100,
        "recorded_at": 250,
        "correlation_id": "correlation-1",
        "causation_id": "cause-1",
        "source": "crm",
        "payload": {"status": "active"},
        "evidence_ids": ("evidence-1", "evidence-2"),
    }


def test_canonical_business_event_contract_reads_legacy_v1_without_new_metadata() -> None:
    legacy = _fact().as_event()
    for key in ("actor_id", "agent_id", "causation_id", "recorded_at_ms", "evidence_ids"):
        legacy["payload"].pop(key, None)

    contract = canonical_business_event_contract(legacy)
    assert contract["actor_id"] is None
    assert contract["agent_id"] is None
    assert contract["causation_id"] is None
    assert contract["recorded_at"] == 200
    assert contract["evidence_ids"] == ()


def test_canonical_business_event_contract_rejects_unknown_schema() -> None:
    event = _fact().as_event()
    event["payload"]["schema_version"] = 999
    with pytest.raises(ValueError, match="unsupported business fact schema_version"):
        canonical_business_event_contract(event)
