from __future__ import annotations

from decimal import Decimal

import pytest

from application.expense import (
    EXPENSE_RECORDED,
    ExpenseHistoryInvariantViolation,
    ExpenseProjector,
    ExpenseRegistry,
)
from contracts.event_store import BUSINESS_FACT_EVENT_TYPE, BusinessFactV1, canonical_business_event_contract
from core.finance.enums import ExpenseCategory, ExpenseLifecycleStatus
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.platform.event_store.memory_event_store import MemoryEventStore


def _registry(events=None, claims=None):
    events = events or MemoryEventStore()
    claims = claims or InMemoryIdempotencyStore()
    return ExpenseRegistry(event_store=events, idempotency_store=claims), events


def test_expense_record_is_idempotent_and_pii_free() -> None:
    registry, events = _registry()
    first = registry.record(
        tenant_id="tenant", business_id="business", expense_id="expense-1",
        idempotency_key="record-1", amount="125.50", currency="eur",
        category=ExpenseCategory.TOOLS, incurred_at_ms=100, recorded_at_ms=120,
    )
    replay = registry.record(
        tenant_id="tenant", business_id="business", expense_id="expense-1",
        idempotency_key="record-1", amount=Decimal("125.5000"), currency="EUR",
        category="tools", incurred_at_ms=100, recorded_at_ms=999,
    )
    assert first == replay
    assert first.amount == Decimal("125.50") and first.currency == "EUR"
    rows = list(events.iter_events(tenant_id="tenant", start_ms=0, event_type=BUSINESS_FACT_EVENT_TYPE))
    assert len(rows) == 1
    payload = dict(dict(rows[0]["payload"])["payload"])
    assert payload == {
        "schema_version": 1, "amount": "125.5", "currency": "EUR",
        "category": "tools", "incurred_at_ms": 100,
    }
    assert "description" not in str(payload).lower()



def test_expense_metadata_propagates_and_same_key_replay_rejects_change() -> None:
    registry, events = _registry()
    record_metadata = {
        "actor_id": "owner-1",
        "decision_id": "decision-record",
        "evidence_ids": ("receipt-1",),
    }
    recorded = registry.record(
        tenant_id="tenant", business_id="business", expense_id="expense-1",
        idempotency_key="record-meta", amount="125.50", currency="EUR",
        category="tools", incurred_at_ms=100, recorded_at_ms=120,
        event_metadata=record_metadata,
    )
    assert registry.record(
        tenant_id="tenant", business_id="business", expense_id="expense-1",
        idempotency_key="record-meta", amount="125.500", currency="eur",
        category="tools", incurred_at_ms=100, recorded_at_ms=999,
        event_metadata=record_metadata,
    ) == recorded
    rows = list(events.iter_events(
        tenant_id="tenant", start_ms=0, event_type=BUSINESS_FACT_EVENT_TYPE
    ))
    assert len(rows) == 1
    contract = canonical_business_event_contract(rows[0])
    assert contract["actor_id"] == "owner-1"
    assert contract["evidence_ids"] == ("receipt-1",)
    with pytest.raises(ValueError, match="event metadata"):
        registry.record(
            tenant_id="tenant", business_id="business", expense_id="expense-1",
            idempotency_key="record-meta", amount="125.50", currency="EUR",
            category="tools", incurred_at_ms=100, recorded_at_ms=120,
            event_metadata={**record_metadata, "actor_id": "owner-2"},
        )

    void_metadata = {"actor_id": "owner-1", "decision_id": "decision-void"}
    voided = registry.void(
        tenant_id="tenant", business_id="business", expense_id="expense-1",
        idempotency_key="void-meta", occurred_at_ms=200, event_metadata=void_metadata,
    )
    assert registry.void(
        tenant_id="tenant", business_id="business", expense_id="expense-1",
        idempotency_key="void-meta", occurred_at_ms=999, event_metadata=void_metadata,
    ) == voided
    with pytest.raises(ValueError, match="event metadata"):
        registry.void(
            tenant_id="tenant", business_id="business", expense_id="expense-1",
            idempotency_key="void-meta", occurred_at_ms=200,
            event_metadata={**void_metadata, "actor_id": "owner-2"},
        )


def test_expense_rejects_negative_incurred_time() -> None:
    registry, _ = _registry()
    with pytest.raises(ValueError, match="incurred_at_ms"):
        registry.record(
            tenant_id="t", business_id="b", expense_id="e", idempotency_key="r",
            amount="10", currency="USD", category="other", incurred_at_ms=-1,
        )

def test_expense_rejects_conflicting_immutable_money() -> None:
    registry, _ = _registry()
    registry.record(
        tenant_id="t", business_id="b", expense_id="e", idempotency_key="r1",
        amount="10", currency="USD", category="operations", incurred_at_ms=1,
    )
    with pytest.raises(ValueError, match="different immutable"):
        registry.record(
            tenant_id="t", business_id="b", expense_id="e", idempotency_key="r2",
            amount="11", currency="USD", category="operations", incurred_at_ms=1,
        )


def test_expense_void_is_terminal_and_idempotent() -> None:
    registry, _ = _registry()
    registry.record(
        tenant_id="t", business_id="b", expense_id="e", idempotency_key="record",
        amount="50", currency="RUB", category="tax", incurred_at_ms=10, recorded_at_ms=20,
    )
    voided = registry.void(
        tenant_id="t", business_id="b", expense_id="e", idempotency_key="void", occurred_at_ms=30,
    )
    replay = registry.void(
        tenant_id="t", business_id="b", expense_id="e", idempotency_key="void-2", occurred_at_ms=40,
    )
    assert voided == replay
    assert voided.lifecycle_status is ExpenseLifecycleStatus.VOIDED
    assert voided.voided_at_ms == 30


def test_expense_projector_fails_closed_on_noncanonical_source() -> None:
    events = MemoryEventStore()
    events.append_event(BusinessFactV1(
        fact_id="bad", tenant_id="t", business_id="b", fact_type=EXPENSE_RECORDED,
        entity_id="e", event_time_ms=1, observed_at_ms=1, source="foreign_writer",
        payload={
            "schema_version": 1, "amount": "10", "currency": "USD",
            "category": "other", "incurred_at_ms": 1,
        },
    ).as_event())
    with pytest.raises(ExpenseHistoryInvariantViolation, match="non-canonical source"):
        ExpenseProjector(events).get(tenant_id="t", business_id="b", expense_id="e")


def test_expense_projector_rejects_unknown_schema() -> None:
    events = MemoryEventStore()
    events.append_event(BusinessFactV1(
        fact_id="bad", tenant_id="t", business_id="b", fact_type=EXPENSE_RECORDED,
        entity_id="e", event_time_ms=1, observed_at_ms=1, source="expense_registry",
        payload={
            "schema_version": 999, "amount": "10", "currency": "USD",
            "category": "other", "incurred_at_ms": 1,
        },
    ).as_event())
    with pytest.raises(ExpenseHistoryInvariantViolation, match="schema version"):
        ExpenseProjector(events).get(tenant_id="t", business_id="b", expense_id="e")


def test_expense_projection_survives_sqlite_restart(tmp_path) -> None:
    from runtime.platform.event_store.sqlite_event_store import SqliteEventStore

    path = tmp_path / "expense.sqlite3"
    claims = InMemoryIdempotencyStore()
    with SqliteEventStore(str(path)) as events:
        registry = ExpenseRegistry(event_store=events, idempotency_store=claims)
        registry.record(
            tenant_id="tenant", business_id="business", expense_id="expense",
            idempotency_key="record", amount="99.95", currency="EUR",
            category="marketing", incurred_at_ms=123, recorded_at_ms=150,
        )
        registry.void(
            tenant_id="tenant", business_id="business", expense_id="expense",
            idempotency_key="void", occurred_at_ms=200,
        )
    with SqliteEventStore(str(path)) as events:
        restored = ExpenseProjector(events).get(
            tenant_id="tenant", business_id="business", expense_id="expense"
        )
    assert restored.amount == Decimal("99.95")
    assert restored.category is ExpenseCategory.MARKETING
    assert restored.lifecycle_status is ExpenseLifecycleStatus.VOIDED
    assert restored.voided_at_ms == 200
