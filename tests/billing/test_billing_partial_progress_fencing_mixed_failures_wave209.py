from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from billing.chargeback_orchestrator import ChargebackOrchestrator
from billing.commercial_cycle_contract import CommercialCollectionResult, InvoiceLifecycleStatus
from billing.dunning_orchestrator import DunningOrchestrator
from billing.invoice_lifecycle import CommercialInvoiceEnvelope, InvoiceLifecycleService
from billing.payment_collection import InMemoryCollectionResultStore, PaymentCollectionOrchestrator
from billing.payment_provider_contract import PaymentCustomerProfile, PaymentProviderContract
from billing.recovery_store import SqliteChargebackStore, SqliteRefundStore
from billing.refund_orchestrator import RefundOrchestrator
from billing.scheduler import DunningRetryJob, SqliteBillingJobLeaseStore, SqliteBillingJobRunStore, create_job_lease
from billing.scheduler.queue_bridge import BillingQueueJobSpec, dispatch_billing_job
from billing.sqlite_store import SqliteLedgerStore
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



def _issued_invoice(*, tenant_id: str, invoice_id: str, total_minor: int) -> CommercialInvoiceEnvelope:
    return CommercialInvoiceEnvelope(
        tenant_id=tenant_id,
        invoice_id=invoice_id,
        subscription_id='sub-1',
        currency='USD',
        subtotal_minor=total_minor - 100,
        tax_minor=100,
        total_minor=total_minor,
        status=InvoiceLifecycleStatus.ISSUED,
        issued_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
    )



def test_dunning_partial_progress_restart_executes_only_remaining_attempts(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    metrics = TenantMetricsRegistry()
    orchestrator = DunningOrchestrator(metrics=metrics)
    orchestrator.open_run(tenant_id='tenant-a', invoice_id='inv-partial', started_at=now - timedelta(days=10))
    orchestrator.mark_action_executed(tenant_id='tenant-a', invoice_id='inv-partial', attempt_no=1)

    run_store_path = str(tmp_path / 'job-runs.sqlite3')
    lease_store_path = str(tmp_path / 'job-leases.sqlite3')
    job = DunningRetryJob(
        orchestrator=orchestrator,
        run_store=SqliteBillingJobRunStore(sqlite_path=run_store_path),
        lease_store=SqliteBillingJobLeaseStore(sqlite_path=lease_store_path),
        worker_id='worker-a',
    )
    executed = job.run(tenant_id='tenant-a', invoice_id='inv-partial', now=now, run_key='safe-rk-dunning')

    restarted = DunningRetryJob(
        orchestrator=orchestrator,
        run_store=SqliteBillingJobRunStore(sqlite_path=run_store_path),
        lease_store=SqliteBillingJobLeaseStore(sqlite_path=lease_store_path),
        worker_id='worker-b',
    )
    replayed = restarted.run(tenant_id='tenant-a', invoice_id='inv-partial', now=now + timedelta(minutes=2), run_key='safe-rk-dunning')

    assert executed == (2, 3)
    assert replayed == (2, 3)
    snapshot = metrics.snapshot(tenant_id='tenant-a')
    assert snapshot['billing_dunning_runs_opened_total']['value'] == 1.0
    assert snapshot['billing_dunning_actions_pending']['value'] == 3.0



def test_sqlite_job_lease_store_rejects_stale_release_after_expired_reacquire(tmp_path: Path) -> None:
    observed = datetime.now(timezone.utc)
    store = SqliteBillingJobLeaseStore(sqlite_path=str(tmp_path / 'job-leases.sqlite3'))

    first = store.acquire(
        create_job_lease(
            tenant_id='tenant-a',
            job_name='reconciliation',
            run_key='safe-rk-recon',
            worker_id='worker-1',
            acquired_at=observed,
            lease_ttl=timedelta(minutes=1),
        )
    )
    reacquired = store.acquire(
        create_job_lease(
            tenant_id='tenant-a',
            job_name='reconciliation',
            run_key='safe-rk-recon',
            worker_id='worker-2',
            acquired_at=observed + timedelta(minutes=2),
            lease_ttl=timedelta(minutes=5),
        )
    )

    assert reacquired.worker_id == 'worker-2'
    assert reacquired.fencing_token != first.fencing_token
    assert store.release(
        tenant_id='tenant-a',
        job_name='reconciliation',
        run_key='safe-rk-recon',
        fencing_token=first.fencing_token,
    ) is False
    current = store.get(tenant_id='tenant-a', job_name='reconciliation', run_key='safe-rk-recon')
    assert current == reacquired



def test_mixed_billing_failure_chain_is_restart_safe_and_deduped(tmp_path: Path) -> None:
    metrics = TenantMetricsRegistry()
    provider = _Provider()
    lifecycle = InvoiceLifecycleService()
    dispatcher = JobDispatcher(store=InMemoryJobStore(), idempotency_store=InMemoryIdempotencyStore())

    issued = _issued_invoice(tenant_id='tenant-a', invoice_id='inv-mixed-a', total_minor=1000)
    collection = PaymentCollectionOrchestrator(provider=provider, result_store=InMemoryCollectionResultStore())
    paid_invoice, collection_result = collection.collect(invoice=issued, idempotency_key='collect-mixed-1')
    replay_paid_invoice, replay_collection_result = collection.collect(invoice=paid_invoice, idempotency_key='collect-mixed-1')

    ledger_path = str(tmp_path / 'ledger.sqlite3')
    refund_store_path = str(tmp_path / 'refunds.sqlite3')
    chargeback_store_path = str(tmp_path / 'chargebacks.sqlite3')
    refund_orchestrator = RefundOrchestrator(
        provider=provider,
        ledger_store=SqliteLedgerStore(sqlite_path=ledger_path),
        monetization_service=MonetizationService(),
        refund_store=SqliteRefundStore(sqlite_path=refund_store_path),
        metrics=metrics,
    )
    chargeback_orchestrator = ChargebackOrchestrator(
        ledger_store=SqliteLedgerStore(sqlite_path=ledger_path),
        monetization_service=MonetizationService(),
        case_store=SqliteChargebackStore(sqlite_path=chargeback_store_path),
        metrics=metrics,
    )

    refunded_invoice, refund_result, _, refund_posting = refund_orchestrator.refund(
        invoice=paid_invoice,
        user_id='user-1',
        amount_minor=200,
        reason='goodwill',
        idempotency_key='refund-mixed-1',
    )
    replay_refunded_invoice, replay_refund_result, _, replay_refund_posting = RefundOrchestrator(
        provider=provider,
        ledger_store=SqliteLedgerStore(sqlite_path=ledger_path),
        monetization_service=MonetizationService(),
        refund_store=SqliteRefundStore(sqlite_path=refund_store_path),
        metrics=metrics,
    ).refund(
        invoice=refunded_invoice,
        user_id='user-1',
        amount_minor=200,
        reason='goodwill',
        idempotency_key='refund-mixed-1',
    )

    charged_back_invoice, chargeback_case, _, chargeback_posting = chargeback_orchestrator.open_case(
        invoice=refunded_invoice,
        user_id='user-1',
        amount_minor=300,
        reason='dispute',
        idempotency_key='chargeback-mixed-1',
    )
    replay_chargeback_invoice, replay_chargeback_case, _, replay_chargeback_posting = ChargebackOrchestrator(
        ledger_store=SqliteLedgerStore(sqlite_path=ledger_path),
        monetization_service=MonetizationService(),
        case_store=SqliteChargebackStore(sqlite_path=chargeback_store_path),
        metrics=metrics,
    ).open_case(
        invoice=charged_back_invoice,
        user_id='user-1',
        amount_minor=300,
        reason='dispute',
        idempotency_key='chargeback-mixed-1',
    )

    spec = BillingQueueJobSpec(
        tenant_id='tenant-a',
        job_name='reconciliation',
        run_key='safe-rk-mixed-reconciliation',
        payload={'invoice_id': 'inv-mixed-a', 'recovery_chain': 'refund-chargeback'},
    )
    first_dispatch = dispatch_billing_job(dispatcher=dispatcher, spec=spec)
    second_dispatch = dispatch_billing_job(dispatcher=dispatcher, spec=spec)

    assert paid_invoice.status.value == 'paid'
    assert replay_paid_invoice == paid_invoice
    assert replay_collection_result == collection_result

    assert replay_refunded_invoice == refunded_invoice
    assert replay_refund_result == refund_result
    assert replay_refund_posting == refund_posting

    assert replay_chargeback_invoice == charged_back_invoice
    assert replay_chargeback_case == chargeback_case
    assert replay_chargeback_posting == chargeback_posting

    assert first_dispatch.accepted is True
    assert second_dispatch.reason == 'dedupe_existing'
    assert second_dispatch.job_id == first_dispatch.job_id
    assert second_dispatch.dedupe_resolution == 'store_existing'
    assert first_dispatch.request.payload['billing_lineage_root'] == 'billing:invoice:inv-mixed-a'

    snapshot = metrics.snapshot(tenant_id='tenant-a')
    assert snapshot['billing_refunds_total']['value'] == 1.0
    assert snapshot['billing_chargebacks_total']['value'] == 1.0
