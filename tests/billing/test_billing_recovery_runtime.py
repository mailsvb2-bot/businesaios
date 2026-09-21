from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime

import pytest

from billing.chargeback_orchestrator import ChargebackOrchestrator
from billing.dispute_policy import DisputePolicy
from billing.invoice_lifecycle import CommercialInvoiceEnvelope, InvoiceLifecycleService
from billing.ledger_event import LedgerEntry, LedgerPosting
from billing.ledger_store import InMemoryLedgerStore
from billing.payment_provider_contract import PaymentCustomerProfile, PaymentProviderContract
from billing.payment_provider_health_registry import PaymentProviderHealthRegistry
from billing.reconciliation_service import BillingReconciliationService
from billing.refund_orchestrator import RefundOrchestrator
from contracts.event_store import canonical_business_event_contract
from core.events.event_types import REFUND_CREATED
from runtime.monetization import MonetizationService
from runtime.platform.event_store.memory_event_store import MemoryEventStore


@dataclass(frozen=True)
class _Provider(PaymentProviderContract):
    def provider_name(self) -> str:
        return 'DummyGateway'

    def ensure_customer(self, *, tenant_id: str, email: str | None = None, metadata=None):
        return PaymentCustomerProfile(tenant_id=tenant_id, provider_customer_id='cust-1')

    def collect(self, attempt):
        raise NotImplementedError

    def refund(self, *, invoice_id: str, tenant_id: str, amount_minor: int, currency: str, reason: str, metadata=None):
        return {
            'refund_id': f'ref-{invoice_id}-{amount_minor}',
            'external_reference': f'ext-{invoice_id}-{amount_minor}',
            'status': 'processed',
        }


class _SpoofingProvider(_Provider):
    def refund(self, *, invoice_id: str, tenant_id: str, amount_minor: int, currency: str, reason: str, metadata=None):
        return {
            **super().refund(
                invoice_id=invoice_id,
                tenant_id=tenant_id,
                amount_minor=amount_minor,
                currency=currency,
                reason=reason,
                metadata=metadata,
            ),
            "actor_id": "provider-spoof",
            "business_id": "provider-spoof-business",
        }


class _MustNotRefundProvider(_Provider):
    def refund(self, **_kwargs):
        raise AssertionError("provider refund must not be called")


def _paid_invoice() -> CommercialInvoiceEnvelope:
    lifecycle = InvoiceLifecycleService()
    issued = lifecycle.issue(
        CommercialInvoiceEnvelope(
            invoice_id='inv-1', tenant_id='tenant-a', subscription_id='sub-1', currency='USD', subtotal_minor=1000, tax_minor=200, total_minor=1200
        )
    )
    return lifecycle.record_payment(issued, amount_minor=1200)


def test_health_registry_is_case_insensitive() -> None:
    registry = PaymentProviderHealthRegistry()
    registry.mark_failure('DummyGateway', reason='timeout', cooldown_seconds=60, now=datetime(2026, 4, 10, tzinfo=UTC))
    assert registry.get('dummygateway').failure_count == 1
    assert not registry.is_available('DUMMYGATEWAY', now=datetime(2026, 4, 10, 0, 0, 30, tzinfo=UTC))
    assert registry.is_available('dummygateway', now=datetime(2026, 4, 10, 0, 1, 1, tzinfo=UTC))


def test_refund_orchestrator_posts_ledger_and_is_idempotent() -> None:
    invoice = _paid_invoice()
    ledger = InMemoryLedgerStore()
    orchestrator = RefundOrchestrator(provider=_Provider(), ledger_store=ledger, monetization_service=MonetizationService())
    updated, result, refund_record, posting = orchestrator.refund(
        invoice=invoice,
        user_id='user-1',
        amount_minor=200,
        reason='goodwill',
        idempotency_key='idem-1',
    )
    replayed, replay_result, replay_record, replay_posting = orchestrator.refund(
        invoice=invoice,
        user_id='user-1',
        amount_minor=200,
        reason='goodwill',
        idempotency_key='idem-1',
    )
    assert result == replay_result
    assert refund_record.amount_minor == 200
    assert replay_record.amount_minor == 200
    assert updated.paid_minor == 1000
    assert replayed.paid_minor == 1000
    assert posting == replay_posting
    assert len(ledger.list_postings(tenant_id='tenant-a')) == 1
    assert ledger.total_for_account(tenant_id='tenant-a', account_code='billing.accounts.refunds', side='debit') == 200


def test_refund_orchestrator_rejects_refund_above_paid_minor() -> None:
    invoice = _paid_invoice()
    orchestrator = RefundOrchestrator(provider=_Provider(), ledger_store=InMemoryLedgerStore(), monetization_service=MonetizationService())
    with pytest.raises(ValueError):
        orchestrator.refund(invoice=invoice, user_id='user-1', amount_minor=1300, reason='bad', idempotency_key='idem-x')


def test_chargeback_orchestrator_posts_ledger_and_marks_invoice() -> None:
    invoice = _paid_invoice()
    ledger = InMemoryLedgerStore()
    orchestrator = ChargebackOrchestrator(ledger_store=ledger, monetization_service=MonetizationService())
    updated, case, record, posting = orchestrator.open_case(invoice=invoice, user_id='user-1', amount_minor=300, reason='dispute')
    assert case.amount_minor == 300
    assert record.amount_minor == 300
    assert updated.paid_minor == 900
    assert updated.status.value == 'partially_paid'
    assert posting.reference_type == 'chargeback'
    assert ledger.total_for_account(tenant_id='tenant-a', account_code='billing.accounts.chargebacks', side='debit') == 300


def test_dispute_policy_returns_structured_classification() -> None:
    result = DisputePolicy().classify({'duplicate_flag': True, 'attribution_mismatch': True})
    assert result.case_type == 'compound_attribution_duplicate_challenge'
    assert result.severity == 'high'


def test_reconciliation_supports_refunds_and_chargebacks() -> None:
    ledger = InMemoryLedgerStore()
    ledger.append(
        LedgerPosting(
            posting_id='p-1',
            tenant_id='tenant-a',
            reference_type='invoice',
            reference_id='inv-1',
            entries=(
                LedgerEntry(tenant_id='tenant-a', entry_id='1', account_code='billing.accounts.ar', side='debit', amount_minor=1000, currency='USD', reference_type='invoice', reference_id='inv-1'),
                LedgerEntry(tenant_id='tenant-a', entry_id='2', account_code='billing.accounts.revenue', side='credit', amount_minor=1000, currency='USD', reference_type='invoice', reference_id='inv-1'),
            ),
        )
    )
    invoice = CommercialInvoiceEnvelope(invoice_id='inv-1', tenant_id='tenant-a', currency='USD', subtotal_minor=1000, tax_minor=0, total_minor=1000)
    monetization = MonetizationService()
    refund = monetization.record_refund(tenant_id='tenant-a', user_id='user-1', amount_minor=150, currency='USD', reason='goodwill')
    chargeback = monetization.record_chargeback(tenant_id='tenant-a', user_id='user-1', amount_minor=100, currency='USD', reason='dispute')
    report = BillingReconciliationService(ledger_store=ledger).reconcile(
        tenant_id='tenant-a',
        invoices=[invoice],
        usage_rollups=(),
        refunds=[refund],
        chargebacks=[chargeback],
    )
    assert any(item.drift_key == 'net_invoice_vs_ledger' for item in report.drifts)



def test_chargeback_orchestrator_is_idempotent_and_does_not_double_subtract() -> None:
    invoice = _paid_invoice()
    ledger = InMemoryLedgerStore()
    orchestrator = ChargebackOrchestrator(ledger_store=ledger, monetization_service=MonetizationService())
    updated, case, _, posting = orchestrator.open_case(invoice=invoice, user_id='user-1', amount_minor=300, reason='dispute', idempotency_key='cb-1')
    replayed, replay_case, _, replay_posting = orchestrator.open_case(invoice=updated, user_id='user-1', amount_minor=300, reason='dispute', idempotency_key='cb-1')
    assert case == replay_case
    assert posting == replay_posting
    assert replayed == updated
    assert len(ledger.list_postings(tenant_id='tenant-a')) == 1


def test_chargeback_orchestrator_rejects_amount_above_paid_minor() -> None:
    invoice = _paid_invoice()
    orchestrator = ChargebackOrchestrator(ledger_store=InMemoryLedgerStore(), monetization_service=MonetizationService())
    with pytest.raises(ValueError):
        orchestrator.open_case(invoice=invoice, user_id='user-1', amount_minor=1300, reason='dispute', idempotency_key='cb-too-much')


def test_refund_orchestrator_replay_on_updated_invoice_does_not_double_subtract() -> None:
    invoice = _paid_invoice()
    ledger = InMemoryLedgerStore()
    orchestrator = RefundOrchestrator(provider=_Provider(), ledger_store=ledger, monetization_service=MonetizationService())
    updated, result, _, posting = orchestrator.refund(invoice=invoice, user_id='user-1', amount_minor=200, reason='goodwill', idempotency_key='idem-updated')
    replayed, replay_result, _, replay_posting = orchestrator.refund(invoice=updated, user_id='user-1', amount_minor=200, reason='goodwill', idempotency_key='idem-updated')
    assert result == replay_result
    assert replayed == updated
    assert posting == replay_posting
    assert len(ledger.list_postings(tenant_id='tenant-a')) == 1


def test_business_scoped_refund_requires_event_spine() -> None:
    invoice = replace(_paid_invoice(), business_id="business-a")
    orchestrator = RefundOrchestrator(
        provider=_Provider(),
        ledger_store=InMemoryLedgerStore(),
        monetization_service=MonetizationService(),
    )
    with pytest.raises(RuntimeError, match="REFUND_EVENT_STORE_REQUIRED"):
        orchestrator.refund(
            invoice=invoice,
            user_id="user-1",
            amount_minor=200,
            reason="goodwill",
            idempotency_key="idem-no-event-spine",
        )


def test_refund_projects_one_canonical_event_and_repairs_on_replay() -> None:
    invoice = replace(_paid_invoice(), business_id="business-a")
    events = MemoryEventStore()
    ledger = InMemoryLedgerStore()
    orchestrator = RefundOrchestrator(
        provider=_SpoofingProvider(),
        ledger_store=ledger,
        monetization_service=MonetizationService(),
        event_store=events,
    )
    metadata = {
        "actor_id": "caller-spoof",
        "business_id": "caller-spoof-business",
        "decision_id": "decision-refund-1",
        "correlation_id": "correlation-refund-1",
        "causation_id": "intent-refund-1",
        "evidence_ids": ["provider-refund-proof-1"],
    }

    updated, result, _, _ = orchestrator.refund(
        invoice=invoice,
        user_id="user-1",
        amount_minor=200,
        reason="goodwill",
        idempotency_key="idem-event-1",
        metadata=metadata,
    )
    replayed, replay_result, _, _ = orchestrator.refund(
        invoice=updated,
        user_id="different-replay-user",
        amount_minor=200,
        reason="different replay reason",
        idempotency_key="idem-event-1",
        metadata=None,
    )

    assert replay_result == result
    assert replayed == updated
    rows = list(events.iter_events(
        tenant_id="tenant-a",
        start_ms=0,
        event_type=REFUND_CREATED,
    ))
    assert len(rows) == 1
    contract = canonical_business_event_contract(rows[0])
    assert contract["business_id"] == "business-a"
    assert contract["actor_id"] == "user-1"
    assert result.metadata["actor_id"] == "user-1"
    assert result.metadata["business_id"] == "business-a"
    assert contract["schema_version"] == 1
    assert contract["correlation_id"] == "correlation-refund-1"
    assert contract["causation_id"] == "intent-refund-1"
    assert contract["evidence_ids"] == ("provider-refund-proof-1",)
    assert contract["payload"]["refund_id"] == result.refund_id
    assert contract["payload"]["invoice_id"] == "inv-1"
    assert contract["payload"]["amount_minor"] == 200



def test_refund_event_spine_rejects_missing_business_before_provider_call() -> None:
    orchestrator = RefundOrchestrator(
        provider=_MustNotRefundProvider(),
        ledger_store=InMemoryLedgerStore(),
        monetization_service=MonetizationService(),
        event_store=MemoryEventStore(),
    )

    with pytest.raises(RuntimeError, match="REFUND_BUSINESS_SCOPE_REQUIRED"):
        orchestrator.refund(
            invoice=_paid_invoice(),
            user_id="user-1",
            amount_minor=200,
            reason="goodwill",
            idempotency_key="idem-missing-business",
        )


def test_refund_replay_rejects_business_rebinding_from_durable_result() -> None:
    invoice = replace(_paid_invoice(), business_id="business-a")
    events = MemoryEventStore()
    orchestrator = RefundOrchestrator(
        provider=_Provider(),
        ledger_store=InMemoryLedgerStore(),
        monetization_service=MonetizationService(),
        event_store=events,
    )
    updated, result, _, _ = orchestrator.refund(
        invoice=invoice,
        user_id="user-1",
        amount_minor=200,
        reason="goodwill",
        idempotency_key="idem-business-scope",
    )
    assert result.metadata["business_id"] == "business-a"

    with pytest.raises(RuntimeError, match="REFUND_BUSINESS_SCOPE_CONFLICT"):
        orchestrator.refund(
            invoice=replace(updated, business_id="business-b"),
            user_id="user-1",
            amount_minor=200,
            reason="goodwill",
            idempotency_key="idem-business-scope",
        )

    rows = list(events.iter_events(
        tenant_id="tenant-a",
        start_ms=0,
        event_type=REFUND_CREATED,
    ))
    assert len(rows) == 1
    assert canonical_business_event_contract(rows[0])["business_id"] == "business-a"
