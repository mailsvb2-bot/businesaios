from __future__ import annotations

import pytest

from application.business_service import BusinessServiceProjector, BusinessServiceRegistry
from contracts.business_service import BusinessServiceNotFound, BusinessServiceStatus
from contracts.event_store import canonical_business_event_contract
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
    return BusinessServiceRegistry(event_store=events, idempotency_store=InMemoryIdempotencyStore()), events


def test_business_service_lifecycle_is_event_backed_and_idempotent() -> None:
    registry, events = _registry()
    created = registry.create(
        tenant_id="tenant-1", business_id="business-1", service_id="svc-1", idempotency_key="create",
        name="Accounting", category="professional", occurred_at_ms=100,
    )
    assert created.status is BusinessServiceStatus.ACTIVE
    assert created.name == "Accounting"
    assert registry.create(
        tenant_id="tenant-1", business_id="business-1", service_id="svc-1", idempotency_key="create",
        name="Accounting", category="professional", occurred_at_ms=999,
    ) == created
    updated = registry.update(
        tenant_id="tenant-1", business_id="business-1", service_id="svc-1", idempotency_key="update",
        name="Accounting Pro", occurred_at_ms=200,
    )
    assert updated.name == "Accounting Pro"
    assert updated.category == "professional"
    archived = registry.archive(
        tenant_id="tenant-1", business_id="business-1", service_id="svc-1", idempotency_key="archive", occurred_at_ms=300,
    )
    assert archived.status is BusinessServiceStatus.ARCHIVED
    assert len([e for e in events.events if str(dict(e.get("payload") or {}).get("fact_type") or "").startswith("business_service.")]) == 3


def test_business_service_metadata_propagates_and_replay_rejects_change() -> None:
    registry, events = _registry()
    create_metadata = {
        "actor_id": "owner-1",
        "decision_id": "decision-create",
        "evidence_ids": ("evidence-create",),
    }
    created = registry.create(
        tenant_id="tenant-1", business_id="business-1", service_id="svc-1",
        idempotency_key="create-meta", name="Accounting", category="professional",
        occurred_at_ms=100, event_metadata=create_metadata,
    )
    assert registry.create(
        tenant_id="tenant-1", business_id="business-1", service_id="svc-1",
        idempotency_key="create-meta", name="Accounting", category="professional",
        occurred_at_ms=999, event_metadata=create_metadata,
    ) == created
    assert len(events.events) == 1
    contract = canonical_business_event_contract(events.events[0])
    assert contract["actor_id"] == "owner-1"
    assert contract["evidence_ids"] == ("evidence-create",)
    with pytest.raises(ValueError, match="event metadata"):
        registry.create(
            tenant_id="tenant-1", business_id="business-1", service_id="svc-1",
            idempotency_key="create-meta", name="Accounting", category="professional",
            occurred_at_ms=100, event_metadata={**create_metadata, "actor_id": "owner-2"},
        )

    update_metadata = {"actor_id": "owner-1", "decision_id": "decision-update"}
    updated = registry.update(
        tenant_id="tenant-1", business_id="business-1", service_id="svc-1",
        idempotency_key="update-meta", name="Accounting Pro", occurred_at_ms=200,
        event_metadata=update_metadata,
    )
    assert registry.update(
        tenant_id="tenant-1", business_id="business-1", service_id="svc-1",
        idempotency_key="update-meta", name="Accounting Pro", occurred_at_ms=999,
        event_metadata=update_metadata,
    ) == updated
    with pytest.raises(ValueError, match="event metadata"):
        registry.update(
            tenant_id="tenant-1", business_id="business-1", service_id="svc-1",
            idempotency_key="update-meta", name="Accounting Pro", occurred_at_ms=200,
            event_metadata={**update_metadata, "actor_id": "owner-2"},
        )

    archive_metadata = {"actor_id": "owner-1", "decision_id": "decision-archive"}
    archived = registry.archive(
        tenant_id="tenant-1", business_id="business-1", service_id="svc-1",
        idempotency_key="archive-meta", occurred_at_ms=300, event_metadata=archive_metadata,
    )
    assert registry.archive(
        tenant_id="tenant-1", business_id="business-1", service_id="svc-1",
        idempotency_key="archive-meta", occurred_at_ms=999, event_metadata=archive_metadata,
    ) == archived
    with pytest.raises(ValueError, match="event metadata"):
        registry.archive(
            tenant_id="tenant-1", business_id="business-1", service_id="svc-1",
            idempotency_key="archive-meta", occurred_at_ms=300,
            event_metadata={**archive_metadata, "actor_id": "owner-2"},
        )


def test_business_service_scope_and_identity_are_fail_closed() -> None:
    registry, events = _registry()
    registry.create(
        tenant_id="tenant-1", business_id="business-1", service_id="svc-1", idempotency_key="create-1",
        name="One", occurred_at_ms=1,
    )
    with pytest.raises(ValueError, match="different identity metadata"):
        registry.create(
            tenant_id="tenant-1", business_id="business-1", service_id="svc-1", idempotency_key="create-2",
            name="Two", occurred_at_ms=2,
        )
    projector = BusinessServiceProjector(events)
    with pytest.raises(BusinessServiceNotFound):
        projector.get(tenant_id="tenant-1", business_id="other", service_id="svc-1")


def test_archived_business_service_rejects_update() -> None:
    registry, _ = _registry()
    registry.create(
        tenant_id="tenant-1", business_id="business-1", service_id="svc-1", idempotency_key="create", occurred_at_ms=1,
    )
    registry.archive(
        tenant_id="tenant-1", business_id="business-1", service_id="svc-1", idempotency_key="archive", occurred_at_ms=2,
    )
    with pytest.raises(ValueError, match="archived business service"):
        registry.update(
            tenant_id="tenant-1", business_id="business-1", service_id="svc-1", idempotency_key="update",
            name="forbidden", occurred_at_ms=3,
        )
