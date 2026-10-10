from __future__ import annotations

from datetime import UTC, datetime

import pytest

from billing.commercial_cycle_contract import CommercialCollectionResult, InvoiceLifecycleStatus
from billing.invoice_lifecycle import CommercialInvoiceEnvelope
from billing.payment_collection import PaymentCollectionOrchestrator


class _Provider:
    def __init__(self, *, result_tenant: str = "tenant-a") -> None:
        self.calls = 0
        self.result_tenant = result_tenant

    def provider_name(self) -> str:
        return "provider-a"

    def collect(self, attempt):
        self.calls += 1
        return CommercialCollectionResult(
            invoice_id=attempt.invoice_id,
            tenant_id=self.result_tenant,
            provider_name=self.provider_name(),
            successful=True,
            external_reference=f"charge-{self.calls}",
        )


def _issued_invoice() -> CommercialInvoiceEnvelope:
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


def test_collection_replay_is_idempotent_and_does_not_double_charge() -> None:
    provider = _Provider()
    orchestrator = PaymentCollectionOrchestrator(provider=provider)
    invoice = _issued_invoice()

    paid, first = orchestrator.collect(invoice=invoice, idempotency_key="idem-1")
    replayed, second = orchestrator.collect(invoice=paid, idempotency_key="idem-1")

    assert provider.calls == 1
    assert first == second
    assert paid.status is InvoiceLifecycleStatus.PAID
    assert paid.paid_minor == 1000
    assert replayed.status is InvoiceLifecycleStatus.PAID
    assert replayed.paid_minor == 1000


def test_collection_provider_tenant_mismatch_fails_closed() -> None:
    provider = _Provider(result_tenant="tenant-b")
    orchestrator = PaymentCollectionOrchestrator(provider=provider)

    with pytest.raises(ValueError, match="tenant_id mismatch"):
        orchestrator.collect(invoice=_issued_invoice(), idempotency_key="idem-tenant")

    assert provider.calls == 1


def test_collection_requires_nonblank_idempotency_key_before_provider_effect() -> None:
    provider = _Provider()
    orchestrator = PaymentCollectionOrchestrator(provider=provider)

    with pytest.raises(ValueError, match="idempotency_key is required"):
        orchestrator.collect(invoice=_issued_invoice(), idempotency_key="")

    assert provider.calls == 0
