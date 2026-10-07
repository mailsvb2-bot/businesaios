from __future__ import annotations

from datetime import UTC, datetime

import pytest

from billing.commercial_cycle_contract import CommercialCollectionResult, InvoiceLifecycleStatus
from billing.invoice_lifecycle import CommercialInvoiceEnvelope
from billing.payment_collection import PaymentCollectionOrchestrator
from core.events.event_types import PAYMENT_FAILED, PAYMENT_SUCCEEDED


class _EventStore:
    def __init__(self) -> None:
        self.events = []

    def append_event(self, event):
        self.events.append(dict(event))

    def iter_events(self, *, tenant_id, start_ms, end_ms=None, user_id=None, event_type=None):
        del start_ms, end_ms, user_id
        return tuple(
            event
            for event in self.events
            if event["tenant_id"] == tenant_id
            and (event_type is None or event["event_type"] == event_type)
        )


class _Provider:
    def __init__(self, *, successful: bool = True) -> None:
        self.successful = successful
        self.calls = 0

    def provider_name(self) -> str:
        return "provider-a"

    def collect(self, attempt):
        self.calls += 1
        return CommercialCollectionResult(
            invoice_id=attempt.invoice_id,
            tenant_id=attempt.tenant_id,
            provider_name=self.provider_name(),
            successful=self.successful,
            external_reference="charge-1" if self.successful else None,
            failure_reason=None if self.successful else "declined",
            processed_at=datetime(2026, 10, 7, 12, tzinfo=UTC),
        )


def _invoice() -> CommercialInvoiceEnvelope:
    return CommercialInvoiceEnvelope(
        tenant_id="tenant-a",
        business_id="business-a",
        invoice_id="invoice-1",
        subscription_id="subscription-1",
        currency="RUB",
        subtotal_minor=1000,
        total_minor=1000,
        status=InvoiceLifecycleStatus.ISSUED,
        issued_at=datetime(2026, 10, 7, tzinfo=UTC),
    )


def test_successful_collection_projects_durable_payment_outcome_and_replay_is_idempotent() -> None:
    events = _EventStore()
    provider = _Provider(successful=True)
    orchestrator = PaymentCollectionOrchestrator(provider=provider, event_store=events)

    paid, result = orchestrator.collect(invoice=_invoice(), idempotency_key="collect-1")
    replayed, replay_result = orchestrator.collect(invoice=paid, idempotency_key="collect-1")

    assert provider.calls == 1
    assert replay_result == result
    assert replayed.status is InvoiceLifecycleStatus.PAID
    assert len(events.events) == 1
    event = events.events[0]
    assert event["event_type"] == PAYMENT_SUCCEEDED
    assert event["tenant_id"] == "tenant-a"
    assert event["payload"]["business_id"] == "business-a"
    assert event["payload"]["invoice_id"] == "invoice-1"
    assert event["payload"]["subscription_id"] == "subscription-1"
    assert event["payload"]["collected_amount_minor"] == 1000
    assert event["payload"]["idempotency_key"] == "collect-1"


def test_failed_collection_projects_failure_outcome_without_marking_invoice_paid() -> None:
    events = _EventStore()
    provider = _Provider(successful=False)
    orchestrator = PaymentCollectionOrchestrator(provider=provider, event_store=events)

    updated, result = orchestrator.collect(invoice=_invoice(), idempotency_key="collect-failed")

    assert result.successful is False
    assert updated.status is InvoiceLifecycleStatus.ISSUED
    assert len(events.events) == 1
    event = events.events[0]
    assert event["event_type"] == PAYMENT_FAILED
    assert event["payload"]["failure_reason"] == "declined"
    assert event["payload"]["successful"] is False


def test_collection_projection_requires_business_scope_when_event_store_is_enabled() -> None:
    events = _EventStore()
    provider = _Provider()
    invoice = CommercialInvoiceEnvelope(
        tenant_id="tenant-a",
        invoice_id="invoice-1",
        subscription_id="subscription-1",
        currency="RUB",
        subtotal_minor=1000,
        total_minor=1000,
        status=InvoiceLifecycleStatus.ISSUED,
        issued_at=datetime(2026, 10, 7, tzinfo=UTC),
    )
    orchestrator = PaymentCollectionOrchestrator(provider=provider, event_store=events)

    with pytest.raises(RuntimeError, match="PAYMENT_COLLECTION_DURABLE_BUSINESS_SCOPE_REQUIRED"):
        orchestrator.collect(invoice=invoice, idempotency_key="collect-1")


def test_collection_projection_fails_closed_on_event_conflict() -> None:
    events = _EventStore()
    provider = _Provider()
    orchestrator = PaymentCollectionOrchestrator(provider=provider, event_store=events)
    invoice = _invoice()

    orchestrator.collect(invoice=invoice, idempotency_key="collect-1")
    assert len(events.events) == 1
    events.events[0]["payload"]["collected_amount_minor"] = 999

    paid = CommercialInvoiceEnvelope(
        **{
            **invoice.__dict__,
            "status": InvoiceLifecycleStatus.PAID,
            "paid_minor": 1000,
        }
    )
    with pytest.raises(RuntimeError, match="PAYMENT_COLLECTION_EVENT_SPINE_CONFLICT"):
        orchestrator.collect(invoice=paid, idempotency_key="collect-1")
