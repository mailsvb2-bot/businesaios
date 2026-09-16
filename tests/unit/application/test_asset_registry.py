from __future__ import annotations

import pytest

from application.asset import AssetHistoryInvariantViolation, AssetProjector, AssetRegistry
from contracts.asset import ASSET_SCHEMA_VERSION, Asset, AssetLifecycleStatus, AssetNotFound
from contracts.event_store import BusinessFactV1
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


def _registry() -> tuple[AssetRegistry, MemoryEventStore]:
    events = MemoryEventStore()
    return AssetRegistry(event_store=events, idempotency_store=InMemoryIdempotencyStore()), events


def test_asset_lifecycle_is_idempotent_versioned_and_money_safe() -> None:
    registry, events = _registry()
    created = registry.create(
        tenant_id="tenant-1",
        business_id="business-1",
        asset_id="asset-1",
        idempotency_key="create",
        asset_kind="equipment",
        state_key="active",
        book_value_minor=250000,
        currency="rub",
        occurred_at_ms=100,
    )
    assert created.currency == "RUB"
    assert created.schema_version == ASSET_SCHEMA_VERSION
    assert len(events.events) == 1
    replay = registry.create(
        tenant_id="tenant-1",
        business_id="business-1",
        asset_id="asset-1",
        idempotency_key="create",
        asset_kind="equipment",
        state_key="active",
        book_value_minor=250000,
        currency="RUB",
        occurred_at_ms=999,
    )
    assert replay == created
    assert len(events.events) == 1
    updated = registry.update(
        tenant_id="tenant-1",
        business_id="business-1",
        asset_id="asset-1",
        idempotency_key="update",
        state_key="maintenance",
        book_value_minor=230000,
        occurred_at_ms=200,
    )
    assert updated.state_key == "maintenance"
    assert updated.book_value_minor == 230000
    archived = registry.archive(
        tenant_id="tenant-1",
        business_id="business-1",
        asset_id="asset-1",
        idempotency_key="archive",
        occurred_at_ms=300,
    )
    assert archived.lifecycle_status is AssetLifecycleStatus.ARCHIVED


def test_asset_identity_currency_and_archive_are_fail_closed() -> None:
    registry, _ = _registry()
    registry.create(
        tenant_id="t",
        business_id="b",
        asset_id="a",
        idempotency_key="create",
        asset_kind="vehicle",
        book_value_minor=100,
        currency="USD",
        occurred_at_ms=100,
    )
    with pytest.raises(ValueError, match="kind cannot be rewritten"):
        registry.update(tenant_id="t", business_id="b", asset_id="a", idempotency_key="kind", asset_kind="equipment")
    with pytest.raises(ValueError, match="currency cannot be rewritten"):
        registry.update(tenant_id="t", business_id="b", asset_id="a", idempotency_key="currency", currency="EUR")
    registry.archive(tenant_id="t", business_id="b", asset_id="a", idempotency_key="archive", occurred_at_ms=200)
    with pytest.raises(ValueError, match="archived asset"):
        registry.update(tenant_id="t", business_id="b", asset_id="a", idempotency_key="later", state_key="active")


def test_asset_contract_rejects_unsafe_money_and_schema() -> None:
    with pytest.raises(ValueError, match="negative"):
        Asset(asset_id="a", tenant_id="t", business_id="b", asset_kind="equipment", book_value_minor=-1, currency="RUB")
    with pytest.raises(ValueError, match="integer minor-unit"):
        Asset(asset_id="a", tenant_id="t", business_id="b", asset_kind="equipment", book_value_minor=1.5, currency="RUB")
    with pytest.raises(ValueError, match="currency is required"):
        Asset(asset_id="a", tenant_id="t", business_id="b", asset_kind="equipment", book_value_minor=1)
    with pytest.raises(ValueError, match="schema_version"):
        Asset(asset_id="a", tenant_id="t", business_id="b", asset_kind="equipment", schema_version=2)


def test_asset_projection_is_scoped_and_corruption_fails_closed() -> None:
    registry, events = _registry()
    registry.create(tenant_id="t1", business_id="b1", asset_id="shared", idempotency_key="1", asset_kind="equipment", occurred_at_ms=100)
    registry.create(tenant_id="t2", business_id="b2", asset_id="shared", idempotency_key="2", asset_kind="vehicle", occurred_at_ms=100)
    projector = AssetProjector(events)
    assert projector.get(tenant_id="t1", business_id="b1", asset_id="shared").asset_kind == "equipment"
    with pytest.raises(AssetNotFound):
        projector.get(tenant_id="t1", business_id="b2", asset_id="shared")
    corrupted = MemoryEventStore()
    corrupted.append_event(
        BusinessFactV1(
            fact_id="update",
            tenant_id="t",
            business_id="b",
            fact_type="asset.updated",
            entity_id="a",
            event_time_ms=100,
            observed_at_ms=100,
            source="asset_registry",
            payload={"schema_version": 1, "asset_kind": "equipment"},
        ).as_event()
    )
    with pytest.raises(AssetHistoryInvariantViolation, match="begin with exactly one create"):
        AssetProjector(corrupted).get(tenant_id="t", business_id="b", asset_id="a")


def test_asset_projection_survives_sqlite_restart(tmp_path) -> None:
    from runtime.platform.event_store.sqlite_event_store import SqliteEventStore

    path = tmp_path / "asset.sqlite3"
    with SqliteEventStore(str(path)) as events:
        registry = AssetRegistry(event_store=events, idempotency_store=InMemoryIdempotencyStore())
        registry.create(
            tenant_id="tenant",
            business_id="business",
            asset_id="asset",
            idempotency_key="create",
            asset_kind="equipment",
            state_key="active",
            book_value_minor=9000,
            currency="EUR",
            occurred_at_ms=123,
        )
        registry.update(
            tenant_id="tenant",
            business_id="business",
            asset_id="asset",
            idempotency_key="update",
            state_key="maintenance",
            book_value_minor=8000,
            occurred_at_ms=234,
        )
    with SqliteEventStore(str(path)) as events:
        restored = AssetProjector(events).get(tenant_id="tenant", business_id="business", asset_id="asset")
    assert restored.asset_kind == "equipment"
    assert restored.state_key == "maintenance"
    assert restored.book_value_minor == 8000
    assert restored.currency == "EUR"
    assert restored.schema_version == ASSET_SCHEMA_VERSION
