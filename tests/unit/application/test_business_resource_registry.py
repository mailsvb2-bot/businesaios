from __future__ import annotations

import pytest

from application.asset import AssetRegistry
from application.business_resource import (
    BusinessResourceHistoryInvariantViolation,
    BusinessResourceProjector,
    BusinessResourceRegistry,
)
from contracts.business_resource import BusinessResource, BusinessResourceNotFound, ResourceLifecycleStatus
from contracts.event_store import BusinessFactV1, canonical_business_event_contract
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


def _runtime():
    events = MemoryEventStore()
    claims = InMemoryIdempotencyStore()
    return (
        AssetRegistry(event_store=events, idempotency_store=claims),
        BusinessResourceRegistry(event_store=events, idempotency_store=claims),
        events,
    )


def test_business_resource_lifecycle_is_idempotent_and_asset_scoped() -> None:
    assets, resources, events = _runtime()
    assets.create(
        tenant_id="tenant", business_id="business", asset_id="asset-1", idempotency_key="asset-create",
        asset_kind="equipment", occurred_at_ms=100,
    )
    created = resources.create(
        tenant_id="tenant", business_id="business", resource_id="resource-1", idempotency_key="create",
        resource_kind="operational_capacity", state_key="available", asset_id="asset-1", occurred_at_ms=200,
    )
    assert created.asset_id == "asset-1"
    assert created.state_key == "available"
    event_count = len(events.events)
    assert resources.create(
        tenant_id="tenant", business_id="business", resource_id="resource-1", idempotency_key="create",
        resource_kind="operational_capacity", state_key="available", asset_id="asset-1", occurred_at_ms=999,
    ) == created
    assert len(events.events) == event_count
    updated = resources.update(
        tenant_id="tenant", business_id="business", resource_id="resource-1", idempotency_key="update",
        state_key="reserved", occurred_at_ms=300,
    )
    assert updated.state_key == "reserved"
    archived = resources.archive(
        tenant_id="tenant", business_id="business", resource_id="resource-1", idempotency_key="archive",
        occurred_at_ms=400,
    )
    assert archived.lifecycle_status is ResourceLifecycleStatus.ARCHIVED


def test_business_resource_metadata_propagates_and_replay_rejects_change() -> None:
    _, resources, events = _runtime()
    create_metadata = { "actor_id": "owner-1", "decision_id": "decision-create", "evidence_ids": ("resource-evidence-1",), }
    created = resources.create( tenant_id="tenant", business_id="business", resource_id="resource-1", idempotency_key="create-meta", resource_kind="capacity", state_key="available", occurred_at_ms=100, event_metadata=create_metadata, )
    assert resources.create( tenant_id="tenant", business_id="business", resource_id="resource-1", idempotency_key="create-meta", resource_kind="capacity", state_key="available", occurred_at_ms=999, event_metadata=create_metadata, ) == created
    assert canonical_business_event_contract(events.events[0])["actor_id"] == "owner-1"
    with pytest.raises(ValueError, match="event metadata"):
        resources.create( tenant_id="tenant", business_id="business", resource_id="resource-1", idempotency_key="create-meta", resource_kind="capacity", state_key="available", occurred_at_ms=100, event_metadata={**create_metadata, "actor_id": "owner-2"}, )
    update_metadata = {"actor_id": "owner-1", "decision_id": "decision-update"}
    updated = resources.update( tenant_id="tenant", business_id="business", resource_id="resource-1", idempotency_key="update-meta", state_key="reserved", occurred_at_ms=200, event_metadata=update_metadata, )
    assert resources.update( tenant_id="tenant", business_id="business", resource_id="resource-1", idempotency_key="update-meta", state_key="reserved", occurred_at_ms=999, event_metadata=update_metadata, ) == updated
    with pytest.raises(ValueError, match="event metadata"):
        resources.update( tenant_id="tenant", business_id="business", resource_id="resource-1", idempotency_key="update-meta", state_key="reserved", occurred_at_ms=200, event_metadata={**update_metadata, "actor_id": "owner-2"}, )
    archive_metadata = {"actor_id": "owner-1", "decision_id": "decision-archive"}
    archived = resources.archive( tenant_id="tenant", business_id="business", resource_id="resource-1", idempotency_key="archive-meta", occurred_at_ms=300, event_metadata=archive_metadata, )
    assert resources.archive( tenant_id="tenant", business_id="business", resource_id="resource-1", idempotency_key="archive-meta", occurred_at_ms=999, event_metadata=archive_metadata, ) == archived
    with pytest.raises(ValueError, match="event metadata"):
        resources.archive( tenant_id="tenant", business_id="business", resource_id="resource-1", idempotency_key="archive-meta", occurred_at_ms=300, event_metadata={**archive_metadata, "actor_id": "owner-2"}, )


def test_business_resource_requires_same_scope_active_asset_relation() -> None:
    assets, resources, _ = _runtime()
    assets.create(
        tenant_id="tenant", business_id="business-a", asset_id="asset", idempotency_key="asset-a",
        asset_kind="equipment", occurred_at_ms=100,
    )
    with pytest.raises(ValueError, match="canonical asset"):
        resources.create(
            tenant_id="tenant", business_id="business-b", resource_id="r", idempotency_key="r-b",
            resource_kind="capacity", asset_id="asset", occurred_at_ms=200,
        )
    assets.archive(
        tenant_id="tenant", business_id="business-a", asset_id="asset", idempotency_key="archive",
        occurred_at_ms=300,
    )
    with pytest.raises(ValueError, match="active asset"):
        resources.create(
            tenant_id="tenant", business_id="business-a", resource_id="r", idempotency_key="r-a",
            resource_kind="capacity", asset_id="asset", occurred_at_ms=400,
        )


def test_business_resource_kind_and_archive_are_fail_closed() -> None:
    _, resources, _ = _runtime()
    resources.create(
        tenant_id="t", business_id="b", resource_id="r", idempotency_key="c",
        resource_kind="inventory_pool", state_key="ready", occurred_at_ms=100,
    )
    with pytest.raises(ValueError, match="kind cannot be rewritten"):
        resources.update(
            tenant_id="t", business_id="b", resource_id="r", idempotency_key="rewrite",
            resource_kind="staff_pool", occurred_at_ms=200,
        )
    resources.archive(tenant_id="t", business_id="b", resource_id="r", idempotency_key="a", occurred_at_ms=300)
    with pytest.raises(ValueError, match="archived business resource"):
        resources.update(
            tenant_id="t", business_id="b", resource_id="r", idempotency_key="after", state_key="ready",
            occurred_at_ms=400,
        )


def test_business_resource_contract_rejects_invalid_identity_and_schema() -> None:
    with pytest.raises(ValueError, match="invalid resource_kind"):
        BusinessResource(resource_id="r", tenant_id="t", business_id="b", resource_kind="")
    with pytest.raises(ValueError, match="unsupported business resource schema_version"):
        BusinessResource(resource_id="r", tenant_id="t", business_id="b", resource_kind="capacity", schema_version=2)


def test_business_resource_projection_is_scoped_and_corruption_fails_closed() -> None:
    _, resources, events = _runtime()
    resources.create(
        tenant_id="t1", business_id="b1", resource_id="shared", idempotency_key="one",
        resource_kind="capacity", occurred_at_ms=100,
    )
    resources.create(
        tenant_id="t2", business_id="b2", resource_id="shared", idempotency_key="two",
        resource_kind="inventory", occurred_at_ms=100,
    )
    projector = BusinessResourceProjector(events)
    assert projector.get(tenant_id="t1", business_id="b1", resource_id="shared").resource_kind == "capacity"
    with pytest.raises(BusinessResourceNotFound):
        projector.get(tenant_id="t1", business_id="b2", resource_id="shared")

    corrupted = MemoryEventStore()
    corrupted.append_event(BusinessFactV1(
        fact_id="bad", tenant_id="t", business_id="b", fact_type="resource.created", entity_id="r",
        event_time_ms=100, observed_at_ms=100, source="business_resource_registry",
        payload={"schema_version": 2, "resource_kind": "capacity", "state_key": None, "asset_id": None},
    ).as_event())
    with pytest.raises(BusinessResourceHistoryInvariantViolation, match="unsupported schema_version"):
        BusinessResourceProjector(corrupted).get(tenant_id="t", business_id="b", resource_id="r")


def test_business_resource_projection_rejects_rewritten_asset_relation() -> None:
    corrupted = MemoryEventStore()
    corrupted.append_event(BusinessFactV1(
        fact_id="create", tenant_id="t", business_id="b", fact_type="resource.created", entity_id="r",
        event_time_ms=100, observed_at_ms=100, source="business_resource_registry",
        payload={"schema_version": 1, "resource_kind": "capacity", "state_key": "ready", "asset_id": "a1"},
    ).as_event())
    corrupted.append_event(BusinessFactV1(
        fact_id="update", tenant_id="t", business_id="b", fact_type="resource.updated", entity_id="r",
        event_time_ms=200, observed_at_ms=200, source="business_resource_registry",
        payload={"schema_version": 1, "resource_kind": "capacity", "state_key": "ready", "asset_id": "a2"},
    ).as_event())
    with pytest.raises(BusinessResourceHistoryInvariantViolation, match="asset relation cannot be rewritten"):
        BusinessResourceProjector(corrupted).get(tenant_id="t", business_id="b", resource_id="r")


def test_business_resource_projection_survives_sqlite_restart(tmp_path) -> None:
    from runtime.platform.event_store.sqlite_event_store import SqliteEventStore

    path = tmp_path / "resource.sqlite3"
    with SqliteEventStore(str(path)) as events:
        claims = InMemoryIdempotencyStore()
        assets = AssetRegistry(event_store=events, idempotency_store=claims)
        assets.create(
            tenant_id="tenant", business_id="business", asset_id="asset", idempotency_key="asset",
            asset_kind="equipment", occurred_at_ms=100,
        )
        resources = BusinessResourceRegistry(event_store=events, idempotency_store=claims)
        resources.create(
            tenant_id="tenant", business_id="business", resource_id="resource", idempotency_key="create",
            resource_kind="capacity", state_key="available", asset_id="asset", occurred_at_ms=200,
        )
        resources.update(
            tenant_id="tenant", business_id="business", resource_id="resource", idempotency_key="update",
            state_key="reserved", occurred_at_ms=300,
        )
    with SqliteEventStore(str(path)) as events:
        restored = BusinessResourceProjector(events).get(
            tenant_id="tenant", business_id="business", resource_id="resource"
        )
    assert restored.resource_kind == "capacity"
    assert restored.state_key == "reserved"
    assert restored.asset_id == "asset"
