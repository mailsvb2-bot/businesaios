from __future__ import annotations

import pytest

from application.lead import LeadHistoryInvariantViolation, LeadProjector, LeadRegistry
from contracts.event_store import BusinessFactV1, canonical_business_event_contract
from contracts.lead import LeadLifecycleStatus, LeadNotFound
from reliability.idempotency_store import InMemoryIdempotencyStore


class MemoryEventStore:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def append_event(self, event: dict) -> None:
        self.events.append(dict(event))

    def iter_events(self, *, tenant_id: str, start_ms: int, end_ms=None, user_id=None, event_type=None):
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


def _registry() -> tuple[LeadRegistry, MemoryEventStore]:
    events = MemoryEventStore()
    return LeadRegistry(event_store=events, idempotency_store=InMemoryIdempotencyStore()), events


def test_lead_lifecycle_is_pii_minimal_scoped_and_idempotent() -> None:
    registry, events = _registry()
    created = registry.create(
        tenant_id="tenant-1", business_id="business-1", lead_id="lead-1",
        idempotency_key="create-1", source="website", occurred_at_ms=100,
    )
    assert created.source == "website"
    assert created.status is None
    assert created.lifecycle_status is LeadLifecycleStatus.ACTIVE
    assert len(events.events) == 1
    replay = registry.create(
        tenant_id="tenant-1", business_id="business-1", lead_id="lead-1",
        idempotency_key="create-1", source="website", occurred_at_ms=999,
    )
    assert replay == created
    assert len(events.events) == 1

    updated = registry.update(
        tenant_id="tenant-1", business_id="business-1", lead_id="lead-1",
        idempotency_key="qualify-1", status="qualified", occurred_at_ms=200,
    )
    assert updated.source == "website"
    assert updated.status == "qualified"
    assert len(events.events) == 2

    archived = registry.archive(
        tenant_id="tenant-1", business_id="business-1", lead_id="lead-1",
        idempotency_key="archive-1", occurred_at_ms=300,
    )
    assert archived.lifecycle_status is LeadLifecycleStatus.ARCHIVED
    assert archived.archived_at_ms == 300
    assert len(events.events) == 3


def test_lead_lifecycle_propagates_canonical_event_metadata_and_replay_fails_closed() -> None:
    registry, events = _registry()
    create_metadata = {
        "actor_id": "owner-1",
        "decision_id": "decision-create",
        "correlation_id": "lead-flow-1",
        "evidence_ids": ("evidence-create",),
    }
    created = registry.create(
        tenant_id="tenant-1", business_id="business-1", lead_id="lead-1",
        idempotency_key="create-meta", source="website", occurred_at_ms=100,
        event_metadata=create_metadata,
    )
    replay = registry.create(
        tenant_id="tenant-1", business_id="business-1", lead_id="lead-1",
        idempotency_key="create-meta", source="website", occurred_at_ms=999,
        event_metadata=create_metadata,
    )
    assert replay == created
    assert len(events.events) == 1
    created_event = events.events[0]
    assert created_event["decision_id"] == "decision-create"
    assert canonical_business_event_contract(created_event)["actor_id"] == "owner-1"
    assert canonical_business_event_contract(created_event)["evidence_ids"] == ("evidence-create",)
    with pytest.raises(ValueError, match="event metadata"):
        registry.create(
            tenant_id="tenant-1", business_id="business-1", lead_id="lead-1",
            idempotency_key="create-meta", source="website", occurred_at_ms=100,
            event_metadata={**create_metadata, "actor_id": "owner-2"},
        )

    update_metadata = {
        "actor_id": "owner-1",
        "decision_id": "decision-update",
        "correlation_id": "lead-flow-1",
    }
    updated = registry.update(
        tenant_id="tenant-1", business_id="business-1", lead_id="lead-1",
        idempotency_key="update-meta", status="qualified", occurred_at_ms=200,
        event_metadata=update_metadata,
    )
    replayed_update = registry.update(
        tenant_id="tenant-1", business_id="business-1", lead_id="lead-1",
        idempotency_key="update-meta", status="qualified", occurred_at_ms=999,
        event_metadata=update_metadata,
    )
    assert replayed_update == updated
    assert len(events.events) == 2
    with pytest.raises(ValueError, match="event metadata"):
        registry.update(
            tenant_id="tenant-1", business_id="business-1", lead_id="lead-1",
            idempotency_key="update-meta", status="qualified", occurred_at_ms=200,
            event_metadata={**update_metadata, "actor_id": "owner-2"},
        )

    archive_metadata = {"actor_id": "owner-1", "decision_id": "decision-archive"}
    archived = registry.archive(
        tenant_id="tenant-1", business_id="business-1", lead_id="lead-1",
        idempotency_key="archive-meta", occurred_at_ms=300, event_metadata=archive_metadata,
    )
    replayed_archive = registry.archive(
        tenant_id="tenant-1", business_id="business-1", lead_id="lead-1",
        idempotency_key="archive-meta", occurred_at_ms=999, event_metadata=archive_metadata,
    )
    assert replayed_archive == archived
    assert len(events.events) == 3
    with pytest.raises(ValueError, match="event metadata"):
        registry.archive(
            tenant_id="tenant-1", business_id="business-1", lead_id="lead-1",
            idempotency_key="archive-meta", occurred_at_ms=300,
            event_metadata={**archive_metadata, "actor_id": "owner-2"},
        )


def test_lead_source_cannot_be_rewritten_and_archived_lead_cannot_update() -> None:
    registry, _ = _registry()
    registry.create(
        tenant_id="tenant-1", business_id="business-1", lead_id="lead-1",
        idempotency_key="create", source="website", occurred_at_ms=100,
    )
    with pytest.raises(ValueError, match="source cannot be rewritten"):
        registry.update(
            tenant_id="tenant-1", business_id="business-1", lead_id="lead-1",
            idempotency_key="rewrite", source="cold_call", occurred_at_ms=200,
        )
    registry.archive(
        tenant_id="tenant-1", business_id="business-1", lead_id="lead-1",
        idempotency_key="archive", occurred_at_ms=300,
    )
    with pytest.raises(ValueError, match="archived lead"):
        registry.update(
            tenant_id="tenant-1", business_id="business-1", lead_id="lead-1",
            idempotency_key="after-archive", status="won", occurred_at_ms=400,
        )


def test_lead_projection_is_tenant_and_business_scoped() -> None:
    events = MemoryEventStore()
    claims = InMemoryIdempotencyStore()
    registry = LeadRegistry(event_store=events, idempotency_store=claims)
    registry.create(
        tenant_id="tenant-1", business_id="business-1", lead_id="shared",
        idempotency_key="one", source="site-a", occurred_at_ms=100,
    )
    registry.create(
        tenant_id="tenant-2", business_id="business-2", lead_id="shared",
        idempotency_key="two", source="site-b", occurred_at_ms=100,
    )
    projector = LeadProjector(events)
    assert projector.get(tenant_id="tenant-1", business_id="business-1", lead_id="shared").source == "site-a"
    assert projector.get(tenant_id="tenant-2", business_id="business-2", lead_id="shared").source == "site-b"
    with pytest.raises(LeadNotFound):
        projector.get(tenant_id="tenant-1", business_id="business-2", lead_id="shared")


def test_lead_projector_fails_closed_on_corrupted_history() -> None:
    events = MemoryEventStore()
    events.append_event(BusinessFactV1(
        fact_id="lead-corrupt-update", tenant_id="tenant-1", business_id="business-1",
        fact_type="lead.updated", entity_id="lead-1", event_time_ms=100, observed_at_ms=100,
        source="lead_registry", payload={"source": "website", "status": "qualified"},
    ).as_event())
    events.append_event(BusinessFactV1(
        fact_id="lead-corrupt-create", tenant_id="tenant-1", business_id="business-1",
        fact_type="lead.created", entity_id="lead-1", event_time_ms=200, observed_at_ms=200,
        source="lead_registry", payload={"source": "website", "status": None},
    ).as_event())
    with pytest.raises(LeadHistoryInvariantViolation, match="begin with exactly one create"):
        LeadProjector(events).get(tenant_id="tenant-1", business_id="business-1", lead_id="lead-1")


def test_lead_projection_survives_sqlite_event_store_restart(tmp_path) -> None:
    from runtime.platform.event_store.sqlite_event_store import SqliteEventStore

    path = tmp_path / "lead-events.sqlite3"
    with SqliteEventStore(str(path)) as events:
        registry = LeadRegistry(event_store=events, idempotency_store=InMemoryIdempotencyStore())
        registry.create(
            tenant_id="tenant-real", business_id="business-real", lead_id="lead-real",
            idempotency_key="create-real", source="referral", status="new", occurred_at_ms=123,
        )
        registry.update(
            tenant_id="tenant-real", business_id="business-real", lead_id="lead-real",
            idempotency_key="status-real", status="qualified", occurred_at_ms=234,
        )
    with SqliteEventStore(str(path)) as events:
        restored = LeadProjector(events).get(
            tenant_id="tenant-real", business_id="business-real", lead_id="lead-real"
        )
    assert restored.source == "referral"
    assert restored.status == "qualified"
    assert restored.created_at_ms == 123
    assert restored.updated_at_ms == 234
