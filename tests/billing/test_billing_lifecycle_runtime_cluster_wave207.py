from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, UTC

from billing.chargeback_orchestrator import ChargebackOrchestrator
from billing.commercial_cycle_contract import CommercialCollectionAttempt, CommercialCollectionResult
from billing.dispute_orchestrator import DisputeOrchestrator, InMemoryDisputeStore
from billing.dunning_orchestrator import DunningOrchestrator
from billing.invoice_lifecycle import CommercialInvoiceEnvelope, InvoiceLifecycleService
from billing.ledger_event import LedgerEntry, LedgerPosting
from billing.ledger_store import InMemoryLedgerStore
from billing.payment_collection import PaymentCollectionOrchestrator
from billing.payment_provider_contract import PaymentCustomerProfile, PaymentProviderContract
from billing.reconciliation_service import BillingReconciliationService
from billing.refund_orchestrator import RefundOrchestrator
from billing.scheduler.queue_bridge import BillingQueueJobSpec, dispatch_billing_job
from billing.usage_rollup import UsageRollup
from observability.tenant_metrics_registry import TenantMetricsRegistry
from runtime.monetization import MonetizationService
from runtime.queue import InMemoryJobStore, JobDispatcher


@dataclass(frozen=True)
class _Provider(PaymentProviderContract):
    name: str = 'cluster-pay'

    def provider_name(self) -> str:
        return self.name

    def ensure_customer(self, *, tenant_id: str, email: str | None = None, metadata=None):
        return PaymentCustomerProfile(tenant_id=tenant_id, provider_customer_id=f'{self.name}:{tenant_id}')

    def collect(self, attempt: CommercialCollectionAttempt) -> CommercialCollectionResult:
        attempt.validate()
        return CommercialCollectionResult(
            invoice_id=attempt.invoice_id,
            tenant_id=attempt.tenant_id,
            provider_name=self.name,
            successful=True,
            external_reference=f'{self.name}:{attempt.idempotency_key}',
            metadata={'provider_affinity': self.name},
        )

    def refund(self, *, invoice_id: str, tenant_id: str, amount_minor: int, currency: str, reason: str, metadata=None):
        return {
            'refund_id': f'refund:{invoice_id}:{amount_minor}',
            'external_reference': f'{self.name}:refund:{invoice_id}:{amount_minor}',
            'provider_name': self.name,
            'currency': currency,
            'reason': reason,
        }


def _issued_invoice() -> CommercialInvoiceEnvelope:
    lifecycle = InvoiceLifecycleService()
    draft = CommercialInvoiceEnvelope(
        tenant_id='tenant-wave207',
        invoice_id='inv-wave207',
        subscription_id='sub-wave207',
        currency='USD',
        subtotal_minor=1000,
        tax_minor=0,
        total_minor=1000,
        metadata={'provider_name': 'cluster-pay'},
    )
    return lifecycle.issue(
        draft,
        issued_at=datetime(2026, 4, 10, 10, 0, tzinfo=UTC),
        due_at=datetime(2026, 4, 17, 10, 0, tzinfo=UTC),
    )


def test_billing_lifecycle_runtime_cluster_seams_hold_without_shadow_owners() -> None:
    invoice = _issued_invoice()
    provider = _Provider()
    metrics = TenantMetricsRegistry()
    monetization = MonetizationService()
    ledger = InMemoryLedgerStore()

    ledger.append(
        LedgerPosting(
            posting_id='posting-wave207-invoice',
            tenant_id=invoice.tenant_id,
            reference_type='invoice',
            reference_id=invoice.invoice_id,
            entries=(
                LedgerEntry(tenant_id=invoice.tenant_id, entry_id='ar-1', account_code='billing.accounts.ar', side='debit', amount_minor=invoice.total_minor, currency=invoice.currency, reference_type='invoice', reference_id=invoice.invoice_id),
                LedgerEntry(tenant_id=invoice.tenant_id, entry_id='rev-1', account_code='billing.accounts.revenue', side='credit', amount_minor=invoice.total_minor, currency=invoice.currency, reference_type='invoice', reference_id=invoice.invoice_id),
            ),
        )
    )

    dispatcher = JobDispatcher(store=InMemoryJobStore())
    queue_verdict = dispatch_billing_job(
        dispatcher=dispatcher,
        spec=BillingQueueJobSpec(
            tenant_id=invoice.tenant_id,
            job_name='invoice_issue',
            run_key='2026-04-10',
            payload={'invoice_id': invoice.invoice_id},
        ),
    )
    assert queue_verdict.accepted is True
    assert queue_verdict.request.payload['billing_lineage_root'] == f'billing:invoice:{invoice.invoice_id}'

    dunning = DunningOrchestrator(metrics=metrics)
    actions = dunning.open_run(
        tenant_id=invoice.tenant_id,
        invoice_id=invoice.invoice_id,
        started_at=datetime(2026, 4, 10, 10, 5, tzinfo=UTC),
    )
    assert len(actions) == 3
    due = dunning.due_actions(
        tenant_id=invoice.tenant_id,
        invoice_id=invoice.invoice_id,
        now=datetime(2026, 4, 13, 10, 5, tzinfo=UTC),
    )
    assert {item.attempt_no for item in due} == {1, 2}
    dunning.mark_action_executed(tenant_id=invoice.tenant_id, invoice_id=invoice.invoice_id, attempt_no=1)

    collected_invoice, collection_result = PaymentCollectionOrchestrator(provider=provider, metrics=metrics).collect(
        invoice=invoice,
        idempotency_key='collect-wave207',
    )
    assert collection_result.successful is True
    assert collected_invoice.status.value == 'paid'
    assert collected_invoice.paid_minor == 1000

    dispute = DisputeOrchestrator(store=InMemoryDisputeStore(), metrics=metrics).open_case(
        tenant_id=invoice.tenant_id,
        invoice_id=invoice.invoice_id,
        payload={'duplicate_flag': True, 'attribution_mismatch': True},
        idempotency_key='dispute-wave207',
        metadata={'provider_name_hint': provider.provider_name()},
    )
    assert dispute.metadata['billing_lineage_root'] == f'billing:invoice:{invoice.invoice_id}'

    refunded_invoice, refund_result, refund_record, _ = RefundOrchestrator(
        provider=provider,
        ledger_store=ledger,
        monetization_service=monetization,
        metrics=metrics,
    ).refund(
        invoice=collected_invoice,
        user_id='user-wave207',
        amount_minor=200,
        reason='goodwill',
        idempotency_key='refund-wave207',
        metadata={'provider_name': provider.provider_name()},
    )
    assert refund_result.amount_minor == 200
    assert refunded_invoice.paid_minor == 800

    charged_back_invoice, chargeback_case, chargeback_record, _ = ChargebackOrchestrator(
        ledger_store=ledger,
        monetization_service=monetization,
        metrics=metrics,
    ).open_case(
        invoice=refunded_invoice,
        user_id='user-wave207',
        amount_minor=150,
        reason='network_dispute',
        idempotency_key='chargeback-wave207',
    )
    assert chargeback_case.amount_minor == 150
    assert charged_back_invoice.paid_minor == 650
    assert charged_back_invoice.status.value == 'partially_paid'

    report = BillingReconciliationService(ledger_store=ledger, metrics=metrics).reconcile(
        tenant_id=invoice.tenant_id,
        invoices=[charged_back_invoice],
        usage_rollups=[UsageRollup(tenant_id=invoice.tenant_id, meter_key='connector_calls', window_key='2026-04', quantity=4.0)],
        usage_rate_minor_by_meter={'connector_calls': 100},
        refunds=[refund_record],
        chargebacks=[chargeback_record],
    )
    assert any(item.drift_key == 'net_invoice_vs_ledger' for item in report.drifts)

    snapshot = metrics.snapshot(tenant_id=invoice.tenant_id)
    assert snapshot['billing_dunning_runs_opened_total']['value'] == 1.0
    assert snapshot['billing_collection_attempts_total']['value'] == 1.0
    assert snapshot['billing_dispute_cases_total']['value'] == 1.0
    assert snapshot['billing_refunds_total']['value'] == 1.0
    assert snapshot['billing_chargebacks_total']['value'] == 1.0
    assert snapshot['billing_reconciliation_drift_count']['value'] >= 1.0
