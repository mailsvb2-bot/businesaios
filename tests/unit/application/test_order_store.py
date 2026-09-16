from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from contracts.order import Order, OrderLifecycleStatus, OrderNotFound
from lead_outcomes.client_outcome_contract import ClientOutcomeOrder, ClientOutcomePackage
from lead_outcomes.client_outcome_order_store import (
    ClientOutcomeOrderStore,
    OrderStore,
)


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
