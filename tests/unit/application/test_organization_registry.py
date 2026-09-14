from __future__ import annotations

import pytest

from application.organization import OrganizationProjector, OrganizationRegistry
from contracts.organization import OrganizationNotFound, OrganizationStatus
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


def _registry() -> tuple[OrganizationRegistry, MemoryEventStore]:
    events = MemoryEventStore()
    return OrganizationRegistry(event_store=events, idempotency_store=InMemoryIdempotencyStore()), events


def test_organization_lifecycle_is_event_backed_idempotent_and_unknown_first() -> None:
    registry, events = _registry()
    created = registry.create(
        tenant_id="tenant-1",
        business_id="business-1",
        organization_id="org-1",
        idempotency_key="create-1",
        occurred_at_ms=100,
    )
    assert created.name is None
    assert created.organization_type is None
    assert created.status is OrganizationStatus.ACTIVE
    assert len(events.events) == 1

    replay = registry.create(
        tenant_id="tenant-1",
        business_id="business-1",
        organization_id="org-1",
        idempotency_key="create-1",
        occurred_at_ms=100,
    )
    assert replay == created
    assert len(events.events) == 1

    updated = registry.update(
        tenant_id="tenant-1",
        business_id="business-1",
        organization_id="org-1",
        idempotency_key="update-1",
        name="Acme Operations",
        organization_type="operating_entity",
        occurred_at_ms=200,
    )
    assert updated.name == "Acme Operations"
    assert updated.organization_type == "operating_entity"
    assert updated.updated_at_ms == 200

    archived = registry.archive(
        tenant_id="tenant-1",
        business_id="business-1",
        organization_id="org-1",
        idempotency_key="archive-1",
        occurred_at_ms=300,
    )
    assert archived.status is OrganizationStatus.ARCHIVED
    assert archived.archived_at_ms == 300
    assert len(events.events) == 3


def test_organization_idempotency_key_reuse_with_different_update_fails_closed() -> None:
    registry, _ = _registry()
    registry.create(
        tenant_id="tenant-1", business_id="business-1", organization_id="org-1",
        idempotency_key="create", name="One", occurred_at_ms=100,
    )
    registry.update(
        tenant_id="tenant-1", business_id="business-1", organization_id="org-1",
        idempotency_key="same-update", name="Two", occurred_at_ms=200,
    )
    with pytest.raises(RuntimeError, match="rejected_scope_mismatch"):
        registry.update(
            tenant_id="tenant-1", business_id="business-1", organization_id="org-1",
            idempotency_key="same-update", name="Three", occurred_at_ms=300,
        )


def test_organization_projection_is_tenant_and_business_scoped() -> None:
    events = MemoryEventStore()
    claims = InMemoryIdempotencyStore()
    registry = OrganizationRegistry(event_store=events, idempotency_store=claims)
    registry.create(
        tenant_id="tenant-1", business_id="business-1", organization_id="shared",
        idempotency_key="t1", name="Tenant One", occurred_at_ms=100,
    )
    registry.create(
        tenant_id="tenant-2", business_id="business-2", organization_id="shared",
        idempotency_key="t2", name="Tenant Two", occurred_at_ms=100,
    )
    projector = OrganizationProjector(events)
    assert projector.get(tenant_id="tenant-1", business_id="business-1", organization_id="shared").name == "Tenant One"
    assert projector.get(tenant_id="tenant-2", business_id="business-2", organization_id="shared").name == "Tenant Two"
    with pytest.raises(OrganizationNotFound):
        projector.get(tenant_id="tenant-1", business_id="business-2", organization_id="shared")


def test_archived_organization_rejects_update() -> None:
    registry, _ = _registry()
    registry.create(
        tenant_id="tenant-1", business_id="business-1", organization_id="org-1",
        idempotency_key="create", occurred_at_ms=100,
    )
    registry.archive(
        tenant_id="tenant-1", business_id="business-1", organization_id="org-1",
        idempotency_key="archive", occurred_at_ms=200,
    )
    with pytest.raises(ValueError, match="archived organization"):
        registry.update(
            tenant_id="tenant-1", business_id="business-1", organization_id="org-1",
            idempotency_key="update", name="forbidden", occurred_at_ms=300,
        )
