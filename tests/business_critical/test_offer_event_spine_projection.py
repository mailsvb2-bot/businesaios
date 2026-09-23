from __future__ import annotations

import pytest

from contracts.event_store import canonical_business_event_contract
from core.events.event_types import OFFER_CREATED, OFFER_UPDATED
from core.offers.offer_events import project_offer_catalog_event
from runtime.platform.event_store.memory_event_store import MemoryEventStore


def _rows(store: MemoryEventStore, *, event_type: str) -> list[dict]:
    return list(
        store.iter_events(
            tenant_id="tenant-a",
            start_ms=0,
            event_type=event_type,
        )
    )


@pytest.mark.lock
def test_offer_event_spine_projects_canonical_business_event_once() -> None:
    store = MemoryEventStore()

    event_id = project_offer_catalog_event(
        store,
        tenant_id="tenant-a",
        business_id="business-a",
        product_id="crm-pro",
        environment="prod",
        offer_id="offer-1",
        catalog_revision="revision-1",
        mutation_kind="patch_apply",
        created=True,
        decision_id="decision-1",
        correlation_id="correlation-1",
    )
    replayed_id = project_offer_catalog_event(
        store,
        tenant_id="tenant-a",
        business_id="business-a",
        product_id="crm-pro",
        environment="prod",
        offer_id="offer-1",
        catalog_revision="revision-1",
        mutation_kind="patch_apply",
        created=True,
        decision_id="decision-1",
        correlation_id="correlation-1",
    )

    assert replayed_id == event_id
    rows = _rows(store, event_type=OFFER_CREATED)
    assert len(rows) == 1
    canonical = canonical_business_event_contract(rows[0])
    assert canonical["event_type"] == OFFER_CREATED
    assert canonical["business_id"] == "business-a"
    assert canonical["correlation_id"] == "correlation-1"
    assert canonical["payload"]["product_id"] == "crm-pro"
    assert canonical["payload"]["environment"] == "prod"
    assert canonical["payload"]["offer_id"] == "offer-1"
    assert canonical["payload"]["catalog_revision"] == "revision-1"
    assert canonical["payload"]["mutation_kind"] == "patch_apply"


@pytest.mark.lock
def test_offer_event_spine_keeps_businesses_and_revisions_independent() -> None:
    store = MemoryEventStore()

    first = project_offer_catalog_event(
        store,
        tenant_id="tenant-a",
        business_id="business-a",
        product_id="crm-pro",
        environment="prod",
        offer_id="offer-1",
        catalog_revision="revision-1",
        mutation_kind="pricing_change",
    )
    second = project_offer_catalog_event(
        store,
        tenant_id="tenant-a",
        business_id="business-b",
        product_id="crm-pro",
        environment="prod",
        offer_id="offer-1",
        catalog_revision="revision-1",
        mutation_kind="pricing_change",
    )
    third = project_offer_catalog_event(
        store,
        tenant_id="tenant-a",
        business_id="business-a",
        product_id="crm-pro",
        environment="prod",
        offer_id="offer-1",
        catalog_revision="revision-2",
        mutation_kind="pricing_change",
    )

    assert len({first, second, third}) == 3
    rows = _rows(store, event_type=OFFER_UPDATED)
    assert len(rows) == 3
    scopes = {
        (
            canonical_business_event_contract(row)["business_id"],
            canonical_business_event_contract(row)["payload"]["catalog_revision"],
        )
        for row in rows
    }
    assert scopes == {
        ("business-a", "revision-1"),
        ("business-b", "revision-1"),
        ("business-a", "revision-2"),
    }


@pytest.mark.lock
def test_offer_event_spine_rejects_missing_business_scope() -> None:
    store = MemoryEventStore()

    with pytest.raises(RuntimeError, match="BUSINESS_ID_REQUIRED"):
        project_offer_catalog_event(
            store,
            tenant_id="tenant-a",
            business_id="",
            product_id="crm-pro",
            environment="prod",
            offer_id="offer-1",
            catalog_revision="revision-1",
            mutation_kind="patch_apply",
        )
