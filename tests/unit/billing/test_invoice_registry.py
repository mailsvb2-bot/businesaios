from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from billing.commercial_cycle_contract import InvoiceLifecycleStatus
from billing.invoice_lifecycle import CommercialInvoiceEnvelope
from billing.invoice_registry import (
    INVOICE_SCHEMA_VERSION,
    InvoiceHistoryInvariantViolation,
    InvoiceNotFound,
    InvoiceProjector,
    InvoiceRegistry,
)
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


def _draft(invoice_id: str = "inv-1") -> CommercialInvoiceEnvelope:
    return CommercialInvoiceEnvelope(
        tenant_id="tenant-a",
        invoice_id=invoice_id,
        subscription_id="sub-1",
        currency="USD",
        subtotal_minor=900,
        tax_minor=100,
        total_minor=1000,
        metadata={"source": "test"},
    )


def _registry() -> tuple[InvoiceRegistry, MemoryEventStore]:
    events = MemoryEventStore()
    registry = InvoiceRegistry(event_store=events, idempotency_store=InMemoryIdempotencyStore())
    return registry, events


def test_invoice_registry_persists_canonical_lifecycle_and_idempotency() -> None:
    registry, events = _registry()
    created = registry.create(
        business_id="business-a",
        invoice=_draft(),
        idempotency_key="create",
        occurred_at_ms=100,
    )
    assert created.status is InvoiceLifecycleStatus.DRAFT
    before = len(events.events)
    assert registry.create(
        business_id="business-a",
        invoice=_draft(),
        idempotency_key="create",
        occurred_at_ms=999,
    ) == created
    assert len(events.events) == before

    issued_at = datetime(2026, 9, 16, 10, 0, tzinfo=UTC)
    issued = registry.issue(
        tenant_id="tenant-a",
        business_id="business-a",
        invoice_id="inv-1",
        idempotency_key="issue",
        issued_at=issued_at,
        due_at=issued_at + timedelta(days=14),
        occurred_at_ms=200,
    )
    assert issued.status is InvoiceLifecycleStatus.ISSUED

    partial = registry.record_payment(
        tenant_id="tenant-a",
        business_id="business-a",
        invoice_id="inv-1",
        idempotency_key="pay-1",
        amount_minor=400,
        occurred_at_ms=300,
    )
    assert partial.status is InvoiceLifecycleStatus.PARTIALLY_PAID
    assert partial.paid_minor == 400

    paid = registry.record_payment(
        tenant_id="tenant-a",
        business_id="business-a",
        invoice_id="inv-1",
        idempotency_key="pay-2",
        amount_minor=600,
        occurred_at_ms=400,
    )
    assert paid.status is InvoiceLifecycleStatus.PAID
    credited = registry.credit(
        tenant_id="tenant-a",
        business_id="business-a",
        invoice_id="inv-1",
        idempotency_key="credit",
        occurred_at_ms=500,
    )
    assert credited.status is InvoiceLifecycleStatus.CREDITED
    assert registry.list_for_business(tenant_id="tenant-a", business_id="business-a") == (credited,)


def test_invoice_registry_is_business_scoped_and_rejects_conflicting_create() -> None:
    registry, _ = _registry()
    registry.create(business_id="business-a", invoice=_draft(), idempotency_key="create", occurred_at_ms=100)
    with pytest.raises(InvoiceNotFound):
        registry.get(tenant_id="tenant-a", business_id="business-b", invoice_id="inv-1")
    conflicting = CommercialInvoiceEnvelope(
        tenant_id="tenant-a",
        invoice_id="inv-1",
        subscription_id="sub-1",
        currency="EUR",
        subtotal_minor=900,
        tax_minor=100,
        total_minor=1000,
    )
    with pytest.raises(ValueError, match="different canonical state"):
        registry.create(
            business_id="business-a",
            invoice=conflicting,
            idempotency_key="conflict",
            occurred_at_ms=200,
        )


def test_invoice_projection_fails_closed_on_illegal_or_rewritten_history() -> None:
    registry, events = _registry()
    registry.create(business_id="business-a", invoice=_draft(), idempotency_key="create", occurred_at_ms=100)
    corrupt = BusinessFactV1(
        fact_id="corrupt",
        tenant_id="tenant-a",
        business_id="business-a",
        fact_type="invoice.payment_recorded",
        entity_id="inv-1",
        event_time_ms=200,
        observed_at_ms=200,
        source="corrupt",
        payload={
            "schema_version": INVOICE_SCHEMA_VERSION,
            "business_id": "business-a",
            "subscription_id": "sub-1",
            "currency": "USD",
            "subtotal_minor": 900,
            "tax_minor": 100,
            "total_minor": 1000,
            "status": "paid",
            "issued_at": datetime(2026, 9, 16, 10, 0, tzinfo=UTC).isoformat(),
            "due_at": None,
            "paid_minor": 1000,
            "metadata": {"source": "tampered"},
        },
    ).as_event()
    events.append_event(corrupt)
    with pytest.raises(InvoiceHistoryInvariantViolation, match="illegal lifecycle transition|does not match"):
        InvoiceProjector(events).get(
            tenant_id="tenant-a", business_id="business-a", invoice_id="inv-1"
        )



def test_invoice_projection_rejects_unsupported_schema_and_missing_business_scope() -> None:
    registry, events = _registry()
    with pytest.raises(ValueError, match="business_id is required"):
        registry.create(business_id="", invoice=_draft(), idempotency_key="create", occurred_at_ms=100)
    bad = BusinessFactV1(
        fact_id="bad-schema",
        tenant_id="tenant-a",
        business_id="business-a",
        fact_type="invoice.created",
        entity_id="inv-schema",
        event_time_ms=100,
        observed_at_ms=100,
        source="corrupt",
        payload={
            "schema_version": INVOICE_SCHEMA_VERSION + 1,
            "business_id": "business-a",
            "subscription_id": None,
            "currency": "USD",
            "subtotal_minor": 100,
            "tax_minor": 0,
            "total_minor": 100,
            "status": "draft",
            "issued_at": None,
            "due_at": None,
            "paid_minor": 0,
            "metadata": {},
        },
    ).as_event()
    events.append_event(bad)
    with pytest.raises(InvoiceHistoryInvariantViolation, match="unsupported schema_version"):
        InvoiceProjector(events).get(
            tenant_id="tenant-a", business_id="business-a", invoice_id="inv-schema"
        )

def test_invoice_projection_survives_sqlite_restart(tmp_path) -> None:
    from runtime.platform.event_store.sqlite_event_store import SqliteEventStore

    path = tmp_path / "invoice.sqlite3"
    issued_at = datetime(2026, 9, 16, 10, 0, tzinfo=UTC)
    with SqliteEventStore(str(path)) as events:
        registry = InvoiceRegistry(event_store=events, idempotency_store=InMemoryIdempotencyStore())
        registry.create(business_id="business-a", invoice=_draft(), idempotency_key="create", occurred_at_ms=100)
        registry.issue(
            tenant_id="tenant-a",
            business_id="business-a",
            invoice_id="inv-1",
            idempotency_key="issue",
            issued_at=issued_at,
            occurred_at_ms=200,
        )
        registry.record_payment(
            tenant_id="tenant-a",
            business_id="business-a",
            invoice_id="inv-1",
            idempotency_key="pay",
            amount_minor=250,
            occurred_at_ms=300,
        )
    with SqliteEventStore(str(path)) as events:
        restored = InvoiceProjector(events).get(
            tenant_id="tenant-a", business_id="business-a", invoice_id="inv-1"
        )
        with pytest.raises(InvoiceNotFound):
            InvoiceProjector(events).get(
                tenant_id="tenant-a", business_id="other", invoice_id="inv-1"
            )
    assert restored.business_id == "business-a"
    assert restored.status is InvoiceLifecycleStatus.PARTIALLY_PAID
    assert restored.paid_minor == 250
    assert restored.issued_at == issued_at


def test_invoice_transition_replays_are_durable_metadata_checked_and_request_safe() -> None:
    registry, events = _registry()
    create_metadata = {"actor_id": "owner-1", "decision_id": "invoice-create"}
    registry.create( business_id="business-a", invoice=_draft(), idempotency_key="create-meta", occurred_at_ms=100, event_metadata=create_metadata, )
    issued_at = datetime(2026, 9, 18, 10, 0, tzinfo=UTC)
    issue_metadata = {"actor_id": "owner-1", "decision_id": "invoice-issue", "evidence_ids": ("e-invoice",)}
    issued = registry.issue( tenant_id="tenant-a", business_id="business-a", invoice_id="inv-1", idempotency_key="issue-meta", issued_at=issued_at, due_at=issued_at + timedelta(days=14), occurred_at_ms=200, event_metadata=issue_metadata, )
    assert registry.issue( tenant_id="tenant-a", business_id="business-a", invoice_id="inv-1", idempotency_key="issue-meta", issued_at=issued_at, due_at=issued_at + timedelta(days=14), occurred_at_ms=999, event_metadata=issue_metadata, ) == issued
    payment_metadata = {"actor_id": "owner-1", "decision_id": "invoice-pay"}
    partial = registry.record_payment( tenant_id="tenant-a", business_id="business-a", invoice_id="inv-1", idempotency_key="pay-meta", amount_minor=400, occurred_at_ms=300, event_metadata=payment_metadata, )
    before_replay_count = len(events.events)
    assert registry.record_payment( tenant_id="tenant-a", business_id="business-a", invoice_id="inv-1", idempotency_key="pay-meta", amount_minor=400, occurred_at_ms=999, event_metadata=payment_metadata, ) == partial
    assert len(events.events) == before_replay_count
    with pytest.raises(ValueError, match="replay conflicts"):
        registry.record_payment( tenant_id="tenant-a", business_id="business-a", invoice_id="inv-1", idempotency_key="pay-meta", amount_minor=500, occurred_at_ms=999, event_metadata=payment_metadata, )
    with pytest.raises(ValueError, match="event metadata"):
        registry.record_payment( tenant_id="tenant-a", business_id="business-a", invoice_id="inv-1", idempotency_key="pay-meta", amount_minor=400, occurred_at_ms=999, event_metadata={**payment_metadata, "actor_id": "owner-2"}, )
    credited_metadata = {"actor_id": "owner-1", "decision_id": "invoice-credit"}
    credited = registry.credit( tenant_id="tenant-a", business_id="business-a", invoice_id="inv-1", idempotency_key="credit-meta", occurred_at_ms=400, event_metadata=credited_metadata, )
    assert registry.credit( tenant_id="tenant-a", business_id="business-a", invoice_id="inv-1", idempotency_key="credit-meta", occurred_at_ms=999, event_metadata=credited_metadata, ) == credited
    rows = list(events.iter_events(tenant_id="tenant-a", start_ms=0))
    payment_event = next( row for row in rows if canonical_business_event_contract(row)["event_type"] == "invoice.payment_recorded" )
    assert canonical_business_event_contract(payment_event)["actor_id"] == "owner-1"
    assert payment_event["decision_id"] == "invoice-pay"


def test_invoice_void_and_uncollectible_replay_after_terminal_state() -> None:
    registry, _ = _registry()
    registry.create( business_id="business-a", invoice=_draft("inv-void"), idempotency_key="create-void", occurred_at_ms=100, )
    voided = registry.void( tenant_id="tenant-a", business_id="business-a", invoice_id="inv-void", idempotency_key="void-key", occurred_at_ms=200, event_metadata={"actor_id": "owner-1"}, )
    assert registry.void( tenant_id="tenant-a", business_id="business-a", invoice_id="inv-void", idempotency_key="void-key", occurred_at_ms=999, event_metadata={"actor_id": "owner-1"}, ) == voided
    registry.create( business_id="business-a", invoice=_draft("inv-uncollectible"), idempotency_key="create-uncollectible", occurred_at_ms=100, )
    issued_at = datetime(2026, 9, 18, 11, 0, tzinfo=UTC)
    registry.issue( tenant_id="tenant-a", business_id="business-a", invoice_id="inv-uncollectible", idempotency_key="issue-uncollectible", issued_at=issued_at, occurred_at_ms=200, )
    uncollectible = registry.mark_uncollectible( tenant_id="tenant-a", business_id="business-a", invoice_id="inv-uncollectible", idempotency_key="uncollectible-key", occurred_at_ms=300, event_metadata={"actor_id": "owner-1"}, )
    assert registry.mark_uncollectible( tenant_id="tenant-a", business_id="business-a", invoice_id="inv-uncollectible", idempotency_key="uncollectible-key", occurred_at_ms=999, event_metadata={"actor_id": "owner-1"}, ) == uncollectible
