from __future__ import annotations

from dataclasses import fields

import pytest

from application.person import PersonProjector, PersonRegistry
from contracts.event_store import canonical_business_event_contract
from contracts.person import Person, PersonNotFound, PersonStatus
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

    def count_events(self, *, tenant_id: str, start_ms: int, end_ms: int, user_id=None, event_type=None) -> int:
        return sum(1 for _ in self.iter_events(tenant_id=tenant_id, start_ms=start_ms, end_ms=end_ms, user_id=user_id, event_type=event_type))


def _registry():
    events = MemoryEventStore()
    return PersonRegistry(event_store=events, idempotency_store=InMemoryIdempotencyStore()), events


def test_person_contract_is_pii_minimal() -> None:
    assert tuple(field.name for field in fields(Person)) == (
        "person_id", "tenant_id", "business_id", "status", "created_at_ms", "updated_at_ms", "archived_at_ms"
    )


def test_person_lifecycle_is_event_backed_and_idempotent() -> None:
    registry, events = _registry()
    created = registry.create(
        tenant_id="tenant-1", business_id="business-1", person_id="person-1",
        idempotency_key="create-1", occurred_at_ms=100,
    )
    assert created.status is PersonStatus.ACTIVE
    assert len(events.events) == 1
    assert registry.create(
        tenant_id="tenant-1", business_id="business-1", person_id="person-1",
        idempotency_key="create-1", occurred_at_ms=999,
    ) == created
    assert len(events.events) == 1
    archived = registry.archive(
        tenant_id="tenant-1", business_id="business-1", person_id="person-1",
        idempotency_key="archive-1", occurred_at_ms=200,
    )
    assert archived.status is PersonStatus.ARCHIVED
    assert archived.archived_at_ms == 200
    assert len(events.events) == 2


def test_person_projection_is_tenant_and_business_scoped() -> None:
    events = MemoryEventStore()
    claims = InMemoryIdempotencyStore()
    registry = PersonRegistry(event_store=events, idempotency_store=claims)
    registry.create(tenant_id="tenant-a", business_id="business-a", person_id="shared", idempotency_key="a", occurred_at_ms=1)
    registry.create(tenant_id="tenant-b", business_id="business-b", person_id="shared", idempotency_key="b", occurred_at_ms=1)
    projector = PersonProjector(events)
    assert projector.get(tenant_id="tenant-a", business_id="business-a", person_id="shared").tenant_id == "tenant-a"
    assert projector.get(tenant_id="tenant-b", business_id="business-b", person_id="shared").tenant_id == "tenant-b"
    with pytest.raises(PersonNotFound):
        projector.get(tenant_id="tenant-a", business_id="business-b", person_id="shared")


def test_person_idempotency_key_cannot_cross_entity_scope() -> None:
    registry, _ = _registry()
    registry.create(tenant_id="tenant-1", business_id="business-1", person_id="person-1", idempotency_key="same", occurred_at_ms=1)
    with pytest.raises(RuntimeError, match="rejected_scope_mismatch"):
        registry.create(tenant_id="tenant-1", business_id="business-1", person_id="person-2", idempotency_key="same", occurred_at_ms=2)


def test_archived_person_replay_is_idempotent() -> None:
    registry, events = _registry()
    registry.create(tenant_id="tenant-1", business_id="business-1", person_id="person-1", idempotency_key="create", occurred_at_ms=1)
    first = registry.archive(tenant_id="tenant-1", business_id="business-1", person_id="person-1", idempotency_key="archive", occurred_at_ms=2)
    second = registry.archive(tenant_id="tenant-1", business_id="business-1", person_id="person-1", idempotency_key="archive", occurred_at_ms=999)
    assert second == first
    assert len(events.events) == 2


def test_person_event_metadata_propagates_and_replay_rejects_change() -> None:
    registry, events = _registry()
    create_metadata = {"actor_id": "owner-1", "decision_id": "person-create", "evidence_ids": ("e-person",)}
    created = registry.create( tenant_id="tenant-1", business_id="business-1", person_id="person-meta", idempotency_key="create-meta", occurred_at_ms=10, event_metadata=create_metadata, )
    assert registry.create( tenant_id="tenant-1", business_id="business-1", person_id="person-meta", idempotency_key="create-meta", occurred_at_ms=999, event_metadata=create_metadata, ) == created
    person_events = [e for e in events.events if str(dict(e.get("payload") or {}).get("fact_type") or "").startswith("person.")]
    assert canonical_business_event_contract(person_events[0])["actor_id"] == "owner-1"
    with pytest.raises(ValueError, match="event metadata"):
        registry.create( tenant_id="tenant-1", business_id="business-1", person_id="person-meta", idempotency_key="create-meta", occurred_at_ms=10, event_metadata={**create_metadata, "actor_id": "owner-2"}, )
    archive_metadata = {"actor_id": "owner-1", "decision_id": "person-archive"}
    archived = registry.archive( tenant_id="tenant-1", business_id="business-1", person_id="person-meta", idempotency_key="archive-meta", occurred_at_ms=20, event_metadata=archive_metadata, )
    assert registry.archive( tenant_id="tenant-1", business_id="business-1", person_id="person-meta", idempotency_key="archive-meta", occurred_at_ms=999, event_metadata=archive_metadata, ) == archived
    with pytest.raises(ValueError, match="event metadata"):
        registry.archive( tenant_id="tenant-1", business_id="business-1", person_id="person-meta", idempotency_key="archive-meta", occurred_at_ms=20, event_metadata={**archive_metadata, "actor_id": "owner-2"}, )
