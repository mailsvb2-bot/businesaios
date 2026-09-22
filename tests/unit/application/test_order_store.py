from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from contracts.event_store import canonical_business_event_contract
from contracts.order import Order, OrderLifecycleStatus, OrderNotFound
from core.events.event_types import ORDER_CANCELLED, ORDER_CREATED, ORDER_UPDATED
from lead_outcomes.client_outcome_contract import ClientOutcomeOrder, ClientOutcomePackage
from lead_outcomes.client_outcome_order_factory import ClientOutcomeOrderFactory
from lead_outcomes.client_outcome_order_store import (
    ClientOutcomeOrderPersistenceService,
    ClientOutcomeOrderStore,
    OrderStore,
)
from lead_outcomes.client_outcome_package_catalog import ClientOutcomePackageCatalog
from lead_outcomes.client_outcome_selection_service import (
    ClientOutcomeSelectionInput,
    ClientOutcomeSelectionService,
)
from runtime.platform.event_store.memory_event_store import MemoryEventStore


class MemoryBackend:
    def __init__(self) -> None:
        self.rows: dict[str, object] = {}

    def replace(self, key: str, value: object) -> None:
        self.rows[str(key)] = value

    def register_unique(self, key: str, value: object) -> None:
        normalized = str(key)
        if normalized in self.rows:
            raise ValueError(f"duplicate registry key: {normalized}")
        self.rows[normalized] = value

    def get(self, key: str) -> object:
        normalized = str(key)
        if normalized not in self.rows:
            raise KeyError(normalized)
        return self.rows[normalized]

    def maybe_get(self, key: str) -> object | None:
        return self.rows.get(str(key))

    def items(self) -> tuple[tuple[str, object], ...]:
        return tuple(sorted(self.rows.items()))


def _package(package_id: str = "clients-5") -> ClientOutcomePackage:
    return ClientOutcomePackage(
        package_id=package_id,
        label=package_id,
        requested_clients=5,
        price_per_verified_client=50.0,
        currency="EUR",
    )


def _client_order(*, order_id: str = "client-order-1") -> ClientOutcomeOrder:
    return ClientOutcomeOrder(
        order_id=order_id,
        tenant_id="tenant-1",
        business_id="business-1",
        package=_package(),
        created_at=datetime(2026, 9, 1, 12, 0, tzinfo=UTC),
    )

def _legacy_payload(order: ClientOutcomeOrder) -> dict[str, object]:
    return {
        "order_id": order.order_id,
        "tenant_id": order.tenant_id,
        "business_id": order.business_id,
        "package": OrderStore._package_payload(order.package),
        "created_at": order.created_at.isoformat(),
        "metadata": dict(order.metadata),
    }


def test_generic_order_lifecycle_is_scoped_and_terminal() -> None:
    store = OrderStore()
    created = store.create_order(
        Order(
            order_id="order-1",
            tenant_id="tenant-1",
            business_id="business-1",
            order_kind="generic",
            state_key="checkout-1",
            created_at_ms=100,
            updated_at_ms=100,
        )
    )
    assert created.lifecycle_status is OrderLifecycleStatus.ACTIVE
    assert store.get_canonical_order(
        "order-1", tenant_id="tenant-1", business_id="business-1"
    ) == created
    with pytest.raises(OrderNotFound):
        store.get_canonical_order("order-1", tenant_id="tenant-2")

    fulfilled = store.transition_order(
        order_id="order-1",
        tenant_id="tenant-1",
        business_id="business-1",
        lifecycle_status=OrderLifecycleStatus.FULFILLED,
        occurred_at_ms=200,
    )
    assert fulfilled.lifecycle_status is OrderLifecycleStatus.FULFILLED
    assert fulfilled.terminal_at_ms == 200
    assert store.transition_order(
        order_id="order-1",
        tenant_id="tenant-1",
        business_id="business-1",
        lifecycle_status=OrderLifecycleStatus.FULFILLED,
        occurred_at_ms=300,
    ) == fulfilled
    with pytest.raises(ValueError, match="invalid order transition"):
        store.transition_order(
            order_id="order-1",
            tenant_id="tenant-1",
            business_id="business-1",
            lifecycle_status=OrderLifecycleStatus.ARCHIVED,
            occurred_at_ms=300,
        )


def test_client_outcome_store_preserves_public_roundtrip_and_amendment() -> None:
    store = ClientOutcomeOrderStore()
    order = _client_order()
    store.save(order)
    assert store.get_order(order.order_id) == order

    amended_at = order.created_at + timedelta(days=1)
    amended = store.amend_order(
        now=amended_at,
        order_id=order.order_id,
        package=_package("clients-10"),
        metadata={"amendment_fingerprint": "amend-1"},
    )
    assert amended is not None
    assert amended.package.package_id == "clients-10"
    assert amended.metadata["amendment_count"] == 1
    assert amended.metadata["amendment_fingerprints"] == ["amend-1"]
    canonical = store.get_canonical_order(order.order_id)
    assert canonical.updated_at_ms == int(amended_at.timestamp() * 1000)

    store.transition_order(
        order_id=order.order_id,
        tenant_id=order.tenant_id,
        business_id=order.business_id,
        lifecycle_status=OrderLifecycleStatus.CANCELLED,
        occurred_at_ms=canonical.updated_at_ms + 1,
    )
    with pytest.raises(ValueError, match="terminal client outcome order"):
        store.amend_order(
            now=amended_at + timedelta(days=1),
            order_id=order.order_id,
            package=_package("clients-20"),
        )


def test_legacy_namespace_migrates_once_and_detects_later_divergence() -> None:
    canonical_backend = MemoryBackend()
    legacy_backend = MemoryBackend()
    legacy_order = _client_order(order_id="legacy-order-1")
    legacy_backend.replace(legacy_order.order_id, _legacy_payload(legacy_order))

    first = ClientOutcomeOrderStore(
        backend=canonical_backend,
        legacy_backend=legacy_backend,
    )
    assert first.get_order(legacy_order.order_id) == legacy_order
    assert legacy_order.order_id in canonical_backend.rows
    assert legacy_order.order_id in legacy_backend.rows

    amended_at = legacy_order.created_at + timedelta(days=1)
    first.amend_order(
        now=amended_at,
        order_id=legacy_order.order_id,
        package=_package("clients-10"),
    )
    rebuilt = ClientOutcomeOrderStore(
        backend=canonical_backend,
        legacy_backend=legacy_backend,
    )
    assert rebuilt.get_order(legacy_order.order_id).package.package_id == "clients-10"

    divergent = _legacy_payload(legacy_order)
    divergent["metadata"] = {"unexpected": "legacy-write"}
    legacy_backend.replace(legacy_order.order_id, divergent)
    with pytest.raises(RuntimeError, match="diverged after canonical migration"):
        ClientOutcomeOrderStore(
            backend=canonical_backend,
            legacy_backend=legacy_backend,
        )

def test_legacy_order_migration_backfills_event_spine_idempotently() -> None:
    canonical_backend = MemoryBackend()
    legacy_backend = MemoryBackend()
    events = MemoryEventStore()
    legacy_order = _client_order(order_id="legacy-event-order")
    legacy_backend.replace(legacy_order.order_id, _legacy_payload(legacy_order))

    ClientOutcomeOrderStore(
        backend=canonical_backend,
        legacy_backend=legacy_backend,
        event_store=events,
    )
    rows = list(
        events.iter_events(
            tenant_id=legacy_order.tenant_id,
            start_ms=0,
            event_type=ORDER_CREATED,
        )
    )
    assert len(rows) == 1

    ClientOutcomeOrderStore(
        backend=canonical_backend,
        legacy_backend=legacy_backend,
        event_store=events,
    )
    rows = list(
        events.iter_events(
            tenant_id=legacy_order.tenant_id,
            start_ms=0,
            event_type=ORDER_CREATED,
        )
    )
    assert len(rows) == 1


def test_existing_canonical_order_gets_event_when_legacy_migration_is_attached() -> None:
    canonical_backend = MemoryBackend()
    legacy_backend = MemoryBackend()
    events = MemoryEventStore()
    legacy_order = _client_order(order_id="precanonical-event-order")
    ClientOutcomeOrderStore(backend=canonical_backend).save(legacy_order)
    legacy_backend.replace(legacy_order.order_id, _legacy_payload(legacy_order))

    ClientOutcomeOrderStore(
        backend=canonical_backend,
        legacy_backend=legacy_backend,
        event_store=events,
    )
    rows = list(
        events.iter_events(
            tenant_id=legacy_order.tenant_id,
            start_ms=0,
            event_type=ORDER_CREATED,
        )
    )
    assert len(rows) == 1


class _FailEventTypeStore:
    def __init__(self, event_type: str) -> None:
        self.inner = MemoryEventStore()
        self.event_type = event_type
        self.fail_once = True

    def append_event(self, event) -> None:
        if self.fail_once and str(event.get("event_type") or "") == self.event_type:
            self.fail_once = False
            raise RuntimeError("simulated order event append failure")
        self.inner.append_event(event)

    def iter_events(self, **kwargs):
        return self.inner.iter_events(**kwargs)


def test_order_event_spine_projects_create_update_and_terminal_without_pii_metadata() -> None:
    events = MemoryEventStore()
    store = OrderStore(backend=MemoryBackend(), event_store=events)
    order = _client_order(order_id="spine-order")
    store.save(order)

    created_rows = list(
        events.iter_events(tenant_id=order.tenant_id, start_ms=0, event_type=ORDER_CREATED)
    )
    assert len(created_rows) == 1
    created = canonical_business_event_contract(created_rows[0])
    assert created["business_id"] == order.business_id
    assert created["payload"]["order_id"] == order.order_id
    assert "metadata" not in created["payload"]
    assert "specialization" not in created["payload"]

    amended_at = order.created_at + timedelta(days=1)
    amended = store.amend_order(
        now=amended_at,
        order_id=order.order_id,
        package=_package("clients-10"),
        metadata={"amendment_fingerprint": "event-spine-amend"},
    )
    assert amended is not None
    updated_rows = list(
        events.iter_events(tenant_id=order.tenant_id, start_ms=0, event_type=ORDER_UPDATED)
    )
    assert len(updated_rows) == 1
    updated = canonical_business_event_contract(updated_rows[0])
    assert updated["payload"]["specialization"]["package_id"] == "clients-10"
    assert "price_per_verified_client" not in updated["payload"]["specialization"]
    assert "metadata" not in updated["payload"]["specialization"]

    canonical = store.get_canonical_order(order.order_id)
    store.transition_order(
        order_id=order.order_id,
        tenant_id=order.tenant_id,
        business_id=order.business_id,
        lifecycle_status=OrderLifecycleStatus.CANCELLED,
        occurred_at_ms=canonical.updated_at_ms + 1,
    )
    cancelled_rows = list(
        events.iter_events(tenant_id=order.tenant_id, start_ms=0, event_type=ORDER_CANCELLED)
    )
    assert len(cancelled_rows) == 1
    cancelled = canonical_business_event_contract(cancelled_rows[0])
    assert cancelled["payload"]["lifecycle_status"] == OrderLifecycleStatus.CANCELLED.value


def test_order_event_spine_create_retry_repairs_store_to_event_crash_window() -> None:
    backend = MemoryBackend()
    events = _FailEventTypeStore(ORDER_CREATED)
    store = OrderStore(backend=backend, event_store=events)
    order = Order(
        order_id="repair-create",
        tenant_id="tenant-1",
        business_id="business-1",
        order_kind="generic",
        created_at_ms=100,
        updated_at_ms=100,
    )

    with pytest.raises(RuntimeError, match="simulated order event append failure"):
        store.create_order(order)
    assert store.get_canonical_order(order.order_id) == order

    assert store.create_order(order) == order
    rows = list(
        events.iter_events(tenant_id=order.tenant_id, start_ms=0, event_type=ORDER_CREATED)
    )
    assert len(rows) == 1


def test_duplicate_amendment_retry_repairs_missing_order_update_event() -> None:
    events = _FailEventTypeStore(ORDER_UPDATED)
    store = OrderStore(backend=MemoryBackend(), event_store=events)
    catalog = ClientOutcomePackageCatalog.default_catalog()
    service = ClientOutcomeSelectionService(
        package_catalog=catalog,
        order_factory=ClientOutcomeOrderFactory(package_catalog=catalog),
        persistence_service=ClientOutcomeOrderPersistenceService(store=store),
    )
    created = service.create_order(
        now=datetime(2026, 9, 1, 12, 0, tzinfo=UTC),
        request=ClientOutcomeSelectionInput(
            tenant_id="tenant-1",
            business_id="business-1",
            package_id="clients-1",
        ),
    )
    request = ClientOutcomeSelectionInput(
        tenant_id="tenant-1",
        business_id="business-1",
        package_id="clients-5",
    )

    with pytest.raises(RuntimeError, match="simulated order event append failure"):
        service.amend(
            now=datetime(2026, 9, 2, 12, 0, tzinfo=UTC),
            order_id=created.order.order_id,
            request=request,
        )

    repaired = service.amend(
        now=datetime(2026, 9, 2, 12, 0, tzinfo=UTC),
        order_id=created.order.order_id,
        request=request,
    )
    assert repaired is not None
    assert repaired.order.package.package_id == "clients-5"
    rows = list(
        events.iter_events(
            tenant_id="tenant-1",
            start_ms=0,
            event_type=ORDER_UPDATED,
        )
    )
    assert len(rows) == 1


def test_order_store_can_fail_closed_when_event_spine_is_required() -> None:
    with pytest.raises(RuntimeError, match="ORDER_EVENT_STORE_REQUIRED"):
        OrderStore(require_event_spine=True)

