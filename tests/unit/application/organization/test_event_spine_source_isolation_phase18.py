"""Canonical Organization projection must not import another domain's facts."""

import pytest

from application.organization.projector import OrganizationProjector
from application.organization.registry import OrganizationRegistry
from contracts.event_store import BusinessFactV1
from contracts.organization import OrganizationNotFound, OrganizationStatus
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.platform.event_store.memory_event_store import MemoryEventStore


def test_foreign_business_facts_cannot_create_update_or_archive_organization() -> None:
    events = MemoryEventStore()
    writer = OrganizationRegistry(
        event_store=events, idempotency_store=InMemoryIdempotencyStore(),
    )
    read = OrganizationProjector(events)

    def external(kind: str, payload: dict, *, timestamp: int, fact_id: str) -> None:
        events.append_event(BusinessFactV1(
            fact_id=fact_id,
            tenant_id="tenant-a",
            business_id="business-a",
            fact_type=kind,
            entity_id="org-1",
            source="unrelated_domain",
            event_time_ms=timestamp,
            observed_at_ms=timestamp,
            payload=payload,
        ).as_event())

    # Matching fact vocabulary alone cannot create a visible organization.
    external("organization.created", {"name": "Fake organization"},
             timestamp=1, fact_id="foreign-organization-create")
    with pytest.raises(OrganizationNotFound):
        read.get(tenant_id="tenant-a", business_id="business-a", organization_id="org-1")
    assert read.list_for_business(tenant_id="tenant-a", business_id="business-a") == ()

    created = writer.create(
        tenant_id="tenant-a", business_id="business-a", organization_id="org-1",
        idempotency_key="actual-create", name="Real organization",
        occurred_at_ms=100,
    )
    assert created.name == "Real organization"
    external("organization.updated", {"name": "Hijacked"},
             timestamp=1000, fact_id="foreign-organization-update")
    external("organization.archived", {},
             timestamp=2000, fact_id="foreign-organization-archive")

    recovered = OrganizationProjector(events).get(
        tenant_id="tenant-a", business_id="business-a", organization_id="org-1",
    )
    assert recovered == created
    assert recovered.name == "Real organization"
    assert recovered.status is OrganizationStatus.ACTIVE
    assert read.list_for_business(tenant_id="tenant-a", business_id="business-a") == (created,)
