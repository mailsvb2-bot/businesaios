from __future__ import annotations

from decimal import Decimal

import pytest

from application.revenue import (
    REVENUE_RECOGNIZED,
    RevenueHistoryInvariantViolation,
    RevenueProjector,
    RevenueRegistry,
)
from contracts.event_store import BUSINESS_FACT_EVENT_TYPE, BusinessFactV1
from core.finance.enums import RevenueLifecycleStatus
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.platform.event_store.memory_event_store import MemoryEventStore


def _registry(events=None, claims=None):
    events = events or MemoryEventStore()
    claims = claims or InMemoryIdempotencyStore()
    return RevenueRegistry(event_store=events, idempotency_store=claims), events


def test_revenue_recognition_is_idempotent_and_pii_free() -> None:
    registry, events = _registry()
    first = registry.recognize(
        tenant_id="tenant", business_id="business", revenue_id="revenue-1",
        idempotency_key="recognize-1", amount="125.50", currency="eur",
        source_kind="order", source_id="order-1", recognized_at_ms=100,
        recorded_at_ms=120,
    )
    replay = registry.recognize(
        tenant_id="tenant", business_id="business", revenue_id="revenue-1",
        idempotency_key="recognize-1", amount=Decimal("125.5000"), currency="EUR",
        source_kind="order", source_id="order-1", recognized_at_ms=100,
        recorded_at_ms=999,
    )
    assert first == replay
    rows = list(events.iter_events(
        tenant_id="tenant", start_ms=0, event_type=BUSINESS_FACT_EVENT_TYPE
    ))
    assert len(rows) == 1
    payload = dict(dict(rows[0]["payload"])["payload"])
    assert payload == {
        "schema_version": 1,
        "amount": "125.5",
        "currency": "EUR",
        "source_kind": "order",
        "source_id": "order-1",
        "recognized_at_ms": 100,
    }
    assert "description" not in str(payload).lower()
    assert "customer" not in str(payload).lower()


def test_revenue_rejects_conflicting_immutable_recognition() -> None:
    registry, _ = _registry()
    registry.recognize(
        tenant_id="t", business_id="b", revenue_id="r", idempotency_key="k1",
        amount="10", currency="USD", source_kind="order", source_id="o1",
        recognized_at_ms=1,
    )
    with pytest.raises(ValueError, match="different immutable"):
        registry.recognize(
            tenant_id="t", business_id="b", revenue_id="r", idempotency_key="k2",
            amount="11", currency="USD", source_kind="order", source_id="o1",
            recognized_at_ms=1,
        )


def test_revenue_reversal_is_terminal_and_idempotent() -> None:
    registry, _ = _registry()
    registry.recognize(
        tenant_id="t", business_id="b", revenue_id="r", idempotency_key="create",
        amount="50", currency="RUB", source_kind="invoice", source_id="i1",
        recognized_at_ms=10, recorded_at_ms=20,
    )
    reversed_revenue = registry.reverse(
        tenant_id="t", business_id="b", revenue_id="r",
        idempotency_key="reverse", occurred_at_ms=30,
    )
    replay = registry.reverse(
        tenant_id="t", business_id="b", revenue_id="r",
        idempotency_key="reverse-2", occurred_at_ms=40,
    )
    assert reversed_revenue == replay
    assert reversed_revenue.lifecycle_status is RevenueLifecycleStatus.REVERSED
    assert reversed_revenue.reversed_at_ms == 30


def test_revenue_projector_fails_closed_on_noncanonical_source() -> None:
    events = MemoryEventStore()
    events.append_event(BusinessFactV1(
        fact_id="bad", tenant_id="t", business_id="b", fact_type=REVENUE_RECOGNIZED,
        entity_id="r", event_time_ms=1, observed_at_ms=1, source="foreign_writer",
        payload={
            "schema_version": 1, "amount": "10", "currency": "USD",
            "source_kind": "order", "source_id": "o1", "recognized_at_ms": 1,
        },
    ).as_event())
    with pytest.raises(RevenueHistoryInvariantViolation, match="non-canonical source"):
        RevenueProjector(events).get(tenant_id="t", business_id="b", revenue_id="r")


def test_revenue_projector_rejects_unknown_schema() -> None:
    events = MemoryEventStore()
    events.append_event(BusinessFactV1(
        fact_id="bad", tenant_id="t", business_id="b", fact_type=REVENUE_RECOGNIZED,
        entity_id="r", event_time_ms=1, observed_at_ms=1, source="revenue_registry",
        payload={
            "schema_version": 999, "amount": "10", "currency": "USD",
            "source_kind": "order", "source_id": "o1", "recognized_at_ms": 1,
        },
    ).as_event())
    with pytest.raises(RevenueHistoryInvariantViolation, match="schema version"):
        RevenueProjector(events).get(tenant_id="t", business_id="b", revenue_id="r")


def test_revenue_projection_survives_sqlite_restart(tmp_path) -> None:
    from runtime.platform.event_store.sqlite_event_store import SqliteEventStore

    path = tmp_path / "revenue.sqlite3"
    claims = InMemoryIdempotencyStore()
    with SqliteEventStore(str(path)) as events:
        registry = RevenueRegistry(event_store=events, idempotency_store=claims)
        registry.recognize(
            tenant_id="tenant", business_id="business", revenue_id="revenue",
            idempotency_key="record", amount="99.95", currency="EUR",
            source_kind="invoice", source_id="invoice-9", recognized_at_ms=123,
            recorded_at_ms=150,
        )
        registry.reverse(
            tenant_id="tenant", business_id="business", revenue_id="revenue",
            idempotency_key="reverse", occurred_at_ms=200,
        )
    with SqliteEventStore(str(path)) as events:
        restored = RevenueProjector(events).get(
            tenant_id="tenant", business_id="business", revenue_id="revenue"
        )
    assert restored.amount == Decimal("99.95")
    assert restored.source_id == "invoice-9"
    assert restored.lifecycle_status is RevenueLifecycleStatus.REVERSED
    assert restored.reversed_at_ms == 200
