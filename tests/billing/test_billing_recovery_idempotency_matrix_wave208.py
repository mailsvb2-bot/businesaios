from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from billing.chargeback_orchestrator import ChargebackOrchestrator
from billing.commercial_cycle_contract import CommercialCollectionResult
from billing.dunning_orchestrator import DunningOrchestrator
from billing.invoice_lifecycle import CommercialInvoiceEnvelope, InvoiceLifecycleService
from billing.payment_collection import InMemoryCollectionResultStore, PaymentCollectionOrchestrator
from billing.payment_provider_contract import PaymentCustomerProfile, PaymentProviderContract
from billing.recovery_store import SqliteChargebackStore, SqliteRefundStore
from billing.refund_orchestrator import RefundOrchestrator
from billing.scheduler import DunningRetryJob, ReconciliationJob, SqliteBillingJobRunStore
from billing.scheduler.queue_bridge import BillingQueueJobSpec, dispatch_billing_job
from billing.sqlite_store import SqliteLedgerStore
from billing.usage_rollup import UsageRollup
from observability.tenant_metrics_registry import TenantMetricsRegistry
from reliability import InMemoryIdempotencyStore
from runtime.monetization import MonetizationService
from runtime.queue import InMemoryJobStore, JobDispatcher


class _Provider(PaymentProviderContract):
    def provider_name(self) -> str:
        return 'DummyGateway'

    def ensure_customer(self, *, tenant_id: str, email: str | None = None, metadata=None):
        return PaymentCustomerProfile(tenant_id=tenant_id, provider_customer_id=f'cust:{tenant_id}')

    def collect(self, attempt):
        attempt.validate()
        return CommercialCollectionResult(
            invoice_id=attempt.invoice_id,
            tenant_id=attempt.tenant_id,
            provider_name=self.provider_name(),
            successful=True,
            external_reference=f'collect:{attempt.idempotency_key}',
            metadata={'attempt_no': attempt.attempt_no},
        )

    def refund(self, *, invoice_id: str, tenant_id: str, amount_minor: int, currency: str, reason: str, metadata=None):
        return {
            'refund_id': f'ref-{invoice_id}-{amount_minor}',
            'external_reference': f'ext-{invoice_id}-{amount_minor}',
            'status': 'processed',
        }


def _paid_invoice(*, tenant_id: str = 'tenant-a', invoice_id: str = 'inv-1', total_minor: int = 1200) -> CommercialInvoiceEnvelope:
    lifecycle = InvoiceLifecycleService()
    issued = lifecycle.issue(
        CommercialInvoiceEnvelope(
            invoice_id=invoice_id,
            tenant_id=tenant_id,
            subscription_id='sub-1',
            currency='USD',
            subtotal_minor=total_minor - 200,
            tax_minor=200,
            total_minor=total_minor,
        )
    )
    return lifecycle.record_payment(issued, amount_minor=total_minor)


def test_refund_restart_replay_is_durable_and_does_not_duplicate_ledger(tmp_path: Path) -> None:
    invoice = _paid_invoice(invoice_id='inv-refund-restart')
    ledger_path = str(tmp_path / 'refund-ledger.sqlite3')
    refund_path = str(tmp_path / 'refunds.sqlite3')

    first = RefundOrchestrator(
        provider=_Provider(),
        ledger_store=SqliteLedgerStore(sqlite_path=ledger_path),
        monetization_service=MonetizationService(),
        refund_store=SqliteRefundStore(sqlite_path=refund_path),
    )
    updated, result, _, posting = first.refund(
        invoice=invoice,
        user_id='user-1',
        amount_minor=200,
        reason='goodwill',
        idempotency_key='idem-restart',
    )

    restarted = RefundOrchestrator(
        provider=_Provider(),
        ledger_store=SqliteLedgerStore(sqlite_path=ledger_path),
        monetization_service=MonetizationService(),
        refund_store=SqliteRefundStore(sqlite_path=refund_path),
    )
    replayed, replay_result, _, replay_posting = restarted.refund(
        invoice=updated,
        user_id='user-1',
        amount_minor=200,
        reason='goodwill',
        idempotency_key='idem-restart',
    )

    ledger = SqliteLedgerStore(sqlite_path=ledger_path)
    assert replayed == updated
    assert replay_result == result
    assert replay_posting == posting
    assert len(ledger.list_postings(tenant_id='tenant-a')) == 1


def test_chargeback_restart_replay_is_durable_and_does_not_duplicate_ledger(tmp_path: Path) -> None:
    invoice = _paid_invoice(invoice_id='inv-chargeback-restart')
    ledger_path = str(tmp_path / 'chargeback-ledger.sqlite3')
    chargeback_path = str(tmp_path / 'chargebacks.sqlite3')

    first = ChargebackOrchestrator(
        ledger_store=SqliteLedgerStore(sqlite_path=ledger_path),
        monetization_service=MonetizationService(),
        case_store=SqliteChargebackStore(sqlite_path=chargeback_path),
    )
    updated, case, _, posting = first.open_case(
        invoice=invoice,
        user_id='user-1',
        amount_minor=300,
        reason='dispute',
        idempotency_key='cb-restart',
    )

    restarted = ChargebackOrchestrator(
        ledger_store=SqliteLedgerStore(sqlite_path=ledger_path),
        monetization_service=MonetizationService(),
        case_store=SqliteChargebackStore(sqlite_path=chargeback_path),
    )
    replayed, replay_case, _, replay_posting = restarted.open_case(
        invoice=updated,
        user_id='user-1',
        amount_minor=300,
        reason='dispute',
        idempotency_key='cb-restart',
    )

    ledger = SqliteLedgerStore(sqlite_path=ledger_path)
    assert replayed == updated
    assert replay_case == case
    assert replay_posting == posting
    assert len(ledger.list_postings(tenant_id='tenant-a')) == 1


def test_runtime_queue_dispatch_dedupes_billing_job_and_preserves_scope() -> None:
    dispatcher = JobDispatcher(store=InMemoryJobStore(), idempotency_store=InMemoryIdempotencyStore())
    spec = BillingQueueJobSpec(
        tenant_id='tenant-a',
        job_name='reconciliation',
        run_key='recon-2026-04-10T00-00-00Z',
        payload={'invoice_id': 'inv-queue-1'},
    )

    first = dispatch_billing_job(dispatcher=dispatcher, spec=spec)
    second = dispatch_billing_job(dispatcher=dispatcher, spec=spec)

    assert first.accepted is True
    assert first.reason == 'accepted'
    assert second.accepted is True
    assert second.reason == 'dedupe_existing'
    assert second.job_id == first.job_id
    assert second.dedupe_resolution == 'store_existing'
    assert first.request.payload['tenant_queue_scope']['namespace'] == 'billing'
    assert first.request.payload['billing_lineage_root'] == 'billing:invoice:inv-queue-1'


def test_collection_replay_does_not_double_charge_on_updated_invoice() -> None:
    provider = _Provider()
    store = InMemoryCollectionResultStore()
    orchestrator = PaymentCollectionOrchestrator(provider=provider, result_store=store)
    invoice = _paid_invoice(invoice_id='inv-collection-replay', total_minor=500)
    invoice = InvoiceLifecycleService().mark_uncollectible(invoice) if False else invoice  # keep lifecycle import live without changing semantics
    issued = CommercialInvoiceEnvelope(
        invoice_id='inv-collection-replay-2',
        tenant_id='tenant-a',
        subscription_id='sub-1',
        currency='USD',
        subtotal_minor=300,
        tax_minor=50,
        total_minor=350,
        status=__import__('billing.commercial_cycle_contract', fromlist=['InvoiceLifecycleStatus']).InvoiceLifecycleStatus.ISSUED,
        issued_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
    )

    updated, result = orchestrator.collect(invoice=issued, idempotency_key='collect-1')
    replayed, replay_result = orchestrator.collect(invoice=updated, idempotency_key='collect-1')

    assert updated.status.value == 'paid'
    assert replayed == updated
    assert replay_result == result
    assert len(store.list_for_invoice('inv-collection-replay-2', tenant_id='tenant-a')) == 1


def test_dunning_and_reconciliation_jobs_are_restart_safe_with_sqlite_run_store(tmp_path: Path) -> None:
    now = datetime(2026, 4, 10, tzinfo=timezone.utc)
    run_store = SqliteBillingJobRunStore(sqlite_path=str(tmp_path / 'job-runs.sqlite3'))
    metrics = TenantMetricsRegistry()
    orchestrator = DunningOrchestrator(metrics=metrics)
    orchestrator.open_run(tenant_id='tenant-a', invoice_id='inv-dunning-rk', started_at=now - timedelta(days=10))

    first_retry = DunningRetryJob(orchestrator=orchestrator, run_store=run_store)
    first_executed = first_retry.run(tenant_id='tenant-a', invoice_id='inv-dunning-rk', now=now, run_key='rk-dunning')

    restarted_retry = DunningRetryJob(orchestrator=orchestrator, run_store=SqliteBillingJobRunStore(sqlite_path=str(tmp_path / 'job-runs.sqlite3')))
    replay_executed = restarted_retry.run(tenant_id='tenant-a', invoice_id='inv-dunning-rk', now=now, run_key='rk-dunning')

    ledger = SqliteLedgerStore(sqlite_path=str(tmp_path / 'ledger.sqlite3'))
    from billing.ledger_event import LedgerEntry, LedgerPosting
    ledger.append(
        LedgerPosting(
            posting_id='p-rk-1',
            tenant_id='tenant-a',
            reference_type='invoice',
            reference_id='inv-rk-1',
            entries=(
                LedgerEntry(tenant_id='tenant-a', entry_id='d1', account_code='billing.accounts.ar', side='debit', amount_minor=1000, currency='USD', reference_type='invoice', reference_id='inv-rk-1'),
                LedgerEntry(tenant_id='tenant-a', entry_id='c1', account_code='billing.accounts.revenue', side='credit', amount_minor=1000, currency='USD', reference_type='invoice', reference_id='inv-rk-1'),
            ),
        )
    )
    invoice = CommercialInvoiceEnvelope(
        tenant_id='tenant-a',
        invoice_id='inv-rk-1',
        currency='USD',
        subtotal_minor=800,
        tax_minor=200,
        total_minor=1000,
        status=__import__('billing.commercial_cycle_contract', fromlist=['InvoiceLifecycleStatus']).InvoiceLifecycleStatus.ISSUED,
        issued_at=now,
    )
    usage = UsageRollup(tenant_id='tenant-a', meter_key='api.calls', window_key='2026-04-01', quantity=10.0)
    first_recon = ReconciliationJob(service=__import__('billing.reconciliation_service', fromlist=['BillingReconciliationService']).BillingReconciliationService(ledger_store=ledger, metrics=metrics), run_store=run_store)
    first_report = first_recon.run(tenant_id='tenant-a', invoices=(invoice,), usage_rollups=(usage,), now=now, run_key='rk-recon', usage_rate_minor_by_meter={'api.calls': 100})
    restarted_recon = ReconciliationJob(service=__import__('billing.reconciliation_service', fromlist=['BillingReconciliationService']).BillingReconciliationService(ledger_store=SqliteLedgerStore(sqlite_path=str(tmp_path / 'ledger.sqlite3')), metrics=metrics), run_store=SqliteBillingJobRunStore(sqlite_path=str(tmp_path / 'job-runs.sqlite3')))
    replay_report = restarted_recon.run(tenant_id='tenant-a', invoices=(invoice,), usage_rollups=(usage,), now=now, run_key='rk-recon', usage_rate_minor_by_meter={'api.calls': 100})

    assert first_executed == replay_executed
    assert first_report == replay_report
    snapshot = metrics.snapshot(tenant_id='tenant-a')
    assert snapshot['billing_dunning_actions_pending']['value'] >= 0.0
    assert snapshot['billing_reconciliation_drift_count']['value'] == 0.0
