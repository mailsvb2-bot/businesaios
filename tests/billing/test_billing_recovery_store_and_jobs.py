from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from billing.chargeback_orchestrator import ChargebackCase
from billing.commercial_cycle_contract import BillingCycleWindow, SubscriptionCommercialEnvelope, SubscriptionLifecycleStatus
from billing.dunning_orchestrator import DunningOrchestrator
from billing.invoice_lifecycle import CommercialInvoiceEnvelope
from billing.ledger_event import LedgerEntry, LedgerPosting
from billing.reconciliation_service import BillingReconciliationService
from billing.recovery_store import SqliteChargebackStore, SqliteRefundStore
from billing.refund_orchestrator import RefundResult
from billing.scheduler import DunningRetryJob, InMemoryBillingJobLeaseStore, InMemoryBillingJobRunStore, InvoiceIssueJob, ReconciliationJob, RenewalJob, SqliteBillingJobLeaseStore, SqliteBillingJobRunStore, create_job_lease
from billing.sqlite_store import SqliteLedgerStore
from billing.usage_rollup import UsageRollup


def test_sqlite_refund_store_persists_idempotent_results(tmp_path: Path) -> None:
    store = SqliteRefundStore(sqlite_path=str(tmp_path / 'refunds.sqlite3'))
    result = RefundResult(
        tenant_id='tenant-a',
        invoice_id='inv-1',
        refund_id='ref-1',
        amount_minor=500,
        currency='USD',
        provider_name='stripe',
        external_reference='ext-1',
    )
    saved = store.save(result, idempotency_key='idem-1')
    replay = SqliteRefundStore(sqlite_path=str(tmp_path / 'refunds.sqlite3')).save(result, idempotency_key='idem-1')
    assert saved == replay
    assert store.get_by_idempotency(tenant_id='tenant-a', invoice_id='inv-1', idempotency_key='idem-1') == result


def test_sqlite_chargeback_store_persists_cases(tmp_path: Path) -> None:
    store = SqliteChargebackStore(sqlite_path=str(tmp_path / 'chargebacks.sqlite3'))
    case = ChargebackCase(
        tenant_id='tenant-a',
        invoice_id='inv-2',
        user_id='user-1',
        amount_minor=700,
        currency='USD',
        reason='fraud',
    )
    store.save(case)
    loaded = SqliteChargebackStore(sqlite_path=str(tmp_path / 'chargebacks.sqlite3')).list_for_invoice(tenant_id='tenant-a', invoice_id='inv-2')
    assert loaded == (case,)


def test_renewal_job_renews_only_due_active_subscription() -> None:
    now = datetime(2026, 4, 10, tzinfo=timezone.utc)
    due_cycle = BillingCycleWindow(start_at=now - timedelta(days=31), end_at=now - timedelta(days=1), anchor='monthly')
    future_cycle = BillingCycleWindow(start_at=now - timedelta(days=5), end_at=now + timedelta(days=25), anchor='monthly')
    due = SubscriptionCommercialEnvelope(tenant_id='tenant-a', subscription_id='sub-due', plan_id='pro', status=SubscriptionLifecycleStatus.ACTIVE, cycle=due_cycle)
    future = SubscriptionCommercialEnvelope(tenant_id='tenant-a', subscription_id='sub-future', plan_id='pro', status=SubscriptionLifecycleStatus.ACTIVE, cycle=future_cycle)
    job = RenewalJob(run_store=InMemoryBillingJobRunStore())
    updated = job.run(tenant_id='tenant-a', subscriptions=(due, future), now=now, run_key='2026-04-10')
    assert updated[0].cycle.start_at == due_cycle.end_at
    assert updated[1] == future
    replay = job.run(tenant_id='tenant-a', subscriptions=updated, now=now, run_key='2026-04-10')
    assert replay == updated


def test_invoice_issue_job_issues_drafts_once() -> None:
    now = datetime(2026, 4, 10, tzinfo=timezone.utc)
    draft = CommercialInvoiceEnvelope(tenant_id='tenant-a', invoice_id='inv-draft', currency='USD', subtotal_minor=100, tax_minor=20, total_minor=120)
    issued = CommercialInvoiceEnvelope(
        tenant_id='tenant-a',
        invoice_id='inv-issued',
        currency='USD',
        subtotal_minor=100,
        tax_minor=20,
        total_minor=120,
        status=__import__('billing.commercial_cycle_contract', fromlist=['InvoiceLifecycleStatus']).InvoiceLifecycleStatus.ISSUED,
        issued_at=now,
    )
    job = InvoiceIssueJob(run_store=InMemoryBillingJobRunStore())
    result = job.run(tenant_id='tenant-a', invoices=(draft, issued), issued_at=now, due_at=now + timedelta(days=7), run_key='issue-run')
    assert result[0].status.value == 'issued'
    assert result[1] == issued
    assert job.run(tenant_id='tenant-a', invoices=result, issued_at=now, run_key='issue-run') == result


def test_dunning_retry_job_marks_due_actions_executed_once() -> None:
    now = datetime(2026, 4, 10, tzinfo=timezone.utc)
    orchestrator = DunningOrchestrator()
    orchestrator.open_run(tenant_id='tenant-a', invoice_id='inv-3', started_at=now - timedelta(days=10))
    job = DunningRetryJob(orchestrator=orchestrator, run_store=InMemoryBillingJobRunStore())
    executed = job.run(tenant_id='tenant-a', invoice_id='inv-3', now=now, run_key='due-run')
    assert executed
    assert orchestrator.due_actions(tenant_id='tenant-a', invoice_id='inv-3', now=now) == ()
    assert job.run(tenant_id='tenant-a', invoice_id='inv-3', now=now, run_key='due-run') == executed


def test_reconciliation_job_is_stable_under_same_run_key(tmp_path: Path) -> None:
    ledger = SqliteLedgerStore(sqlite_path=str(tmp_path / 'ledger.sqlite3'))
    ledger.append(
        LedgerPosting(
            posting_id='p1',
            tenant_id='tenant-a',
            reference_type='invoice',
            reference_id='inv-4',
            entries=(
                LedgerEntry(tenant_id='tenant-a', entry_id='d1', account_code='billing.accounts.ar', side='debit', amount_minor=1000, currency='USD', reference_type='invoice', reference_id='inv-4'),
                LedgerEntry(tenant_id='tenant-a', entry_id='c1', account_code='billing.accounts.revenue', side='credit', amount_minor=1000, currency='USD', reference_type='invoice', reference_id='inv-4'),
            ),
        )
    )
    service = BillingReconciliationService(ledger_store=ledger)
    job = ReconciliationJob(service=service, run_store=InMemoryBillingJobRunStore())
    invoice = CommercialInvoiceEnvelope(
        tenant_id='tenant-a',
        invoice_id='inv-4',
        currency='USD',
        subtotal_minor=800,
        tax_minor=200,
        total_minor=1000,
        status=__import__('billing.commercial_cycle_contract', fromlist=['InvoiceLifecycleStatus']).InvoiceLifecycleStatus.ISSUED,
        issued_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
    )
    usage = UsageRollup(tenant_id='tenant-a', meter_key='api.calls', window_key='2026-04-01', quantity=10.0)
    first = job.run(tenant_id='tenant-a', invoices=(invoice,), usage_rollups=(usage,), now=datetime(2026, 4, 10, tzinfo=timezone.utc), run_key='recon-1', usage_rate_minor_by_meter={'api.calls': 100})
    second = job.run(tenant_id='tenant-a', invoices=(invoice,), usage_rollups=(usage,), now=datetime(2026, 4, 10, tzinfo=timezone.utc), run_key='recon-1', usage_rate_minor_by_meter={'api.calls': 100})
    assert first.is_clean is True
    assert second.is_clean is True



def test_sqlite_chargeback_store_supports_idempotency(tmp_path: Path) -> None:
    store = SqliteChargebackStore(sqlite_path=str(tmp_path / 'chargebacks-idem.sqlite3'))
    case = ChargebackCase(
        tenant_id='tenant-a',
        invoice_id='inv-2',
        user_id='user-1',
        amount_minor=700,
        currency='USD',
        reason='fraud',
        idempotency_key='idem-case',
    )
    first = store.save(case, idempotency_key='idem-case')
    second = SqliteChargebackStore(sqlite_path=str(tmp_path / 'chargebacks-idem.sqlite3')).save(case, idempotency_key='idem-case')
    assert first == second
    assert store.get_by_idempotency(tenant_id='tenant-a', invoice_id='inv-2', idempotency_key='idem-case') == case


def test_sqlite_job_run_store_persists_runs(tmp_path: Path) -> None:
    store = SqliteBillingJobRunStore(sqlite_path=str(tmp_path / 'job-runs.sqlite3'))
    run = __import__('billing.scheduler', fromlist=['BillingJobRun']).BillingJobRun(
        tenant_id='tenant-a',
        job_name='renewal',
        run_key='2026-04-10',
        started_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
        finished_at=datetime(2026, 4, 10, tzinfo=timezone.utc),
        metadata={'owner': 'test'},
    )
    store.save(run)
    loaded = SqliteBillingJobRunStore(sqlite_path=str(tmp_path / 'job-runs.sqlite3')).get(tenant_id='tenant-a', job_name='renewal', run_key='2026-04-10')
    assert loaded == run


def test_renewal_job_rejects_same_run_key_with_different_input() -> None:
    now = datetime(2026, 4, 10, tzinfo=timezone.utc)
    due_cycle = BillingCycleWindow(start_at=now - timedelta(days=31), end_at=now - timedelta(days=1), anchor='monthly')
    due = SubscriptionCommercialEnvelope(tenant_id='tenant-a', subscription_id='sub-due', plan_id='pro', status=SubscriptionLifecycleStatus.ACTIVE, cycle=due_cycle)
    changed = SubscriptionCommercialEnvelope(tenant_id='tenant-a', subscription_id='sub-due', plan_id='enterprise', status=SubscriptionLifecycleStatus.ACTIVE, cycle=due_cycle)
    job = RenewalJob(run_store=InMemoryBillingJobRunStore())
    job.run(tenant_id='tenant-a', subscriptions=(due,), now=now, run_key='same-key')
    import pytest
    with pytest.raises(ValueError):
        job.run(tenant_id='tenant-a', subscriptions=(changed,), now=now, run_key='same-key')


def test_inmemory_job_lease_store_blocks_parallel_holder() -> None:
    store = InMemoryBillingJobLeaseStore()
    observed = datetime.now(timezone.utc)
    first = create_job_lease(tenant_id='tenant-a', job_name='renewal', run_key='rk1', worker_id='worker-1', acquired_at=observed, lease_ttl=timedelta(days=1))
    store.acquire(first)
    import pytest
    with pytest.raises(RuntimeError):
        store.acquire(create_job_lease(tenant_id='tenant-a', job_name='renewal', run_key='rk1', worker_id='worker-2', acquired_at=observed, lease_ttl=timedelta(days=1)))
    assert store.release(tenant_id='tenant-a', job_name='renewal', run_key='rk1', fencing_token='wrong') is False
    assert store.release(tenant_id='tenant-a', job_name='renewal', run_key='rk1', fencing_token=first.fencing_token) is True
    reacquired = store.acquire(create_job_lease(tenant_id='tenant-a', job_name='renewal', run_key='rk1', worker_id='worker-2', acquired_at=observed + timedelta(minutes=6), lease_ttl=timedelta(days=1)))
    assert reacquired.worker_id == 'worker-2'


def test_sqlite_job_lease_store_persists_and_enforces_fencing(tmp_path: Path) -> None:
    db = str(tmp_path / 'job-leases.sqlite3')
    store = SqliteBillingJobLeaseStore(sqlite_path=db)
    observed = datetime.now(timezone.utc)
    lease = create_job_lease(tenant_id='tenant-a', job_name='invoice_issue', run_key='rk2', worker_id='worker-1', acquired_at=observed, lease_ttl=timedelta(days=1))
    saved = store.acquire(lease)
    loaded = SqliteBillingJobLeaseStore(sqlite_path=db).get(tenant_id='tenant-a', job_name='invoice_issue', run_key='rk2')
    assert loaded == saved
    assert store.release(tenant_id='tenant-a', job_name='invoice_issue', run_key='rk2', fencing_token='wrong') is False
    assert store.get(tenant_id='tenant-a', job_name='invoice_issue', run_key='rk2') == saved
    assert store.release(tenant_id='tenant-a', job_name='invoice_issue', run_key='rk2', fencing_token=saved.fencing_token) is True
    assert store.get(tenant_id='tenant-a', job_name='invoice_issue', run_key='rk2') is None


def test_renewal_job_honors_active_job_lease() -> None:
    now = datetime(2026, 4, 10, tzinfo=timezone.utc)
    due_cycle = BillingCycleWindow(start_at=now - timedelta(days=31), end_at=now - timedelta(days=1), anchor='monthly')
    due = SubscriptionCommercialEnvelope(tenant_id='tenant-a', subscription_id='sub-due', plan_id='pro', status=SubscriptionLifecycleStatus.ACTIVE, cycle=due_cycle)
    lease_store = InMemoryBillingJobLeaseStore()
    blocking = create_job_lease(tenant_id='tenant-a', job_name='renewal', run_key='same-key', worker_id='worker-1', acquired_at=now, lease_ttl=timedelta(minutes=5))
    lease_store.acquire(blocking)
    job = RenewalJob(run_store=InMemoryBillingJobRunStore(), lease_store=lease_store, worker_id='worker-2')
    import pytest
    with pytest.raises(RuntimeError):
        job.run(tenant_id='tenant-a', subscriptions=(due,), now=now, run_key='same-key')


def test_job_lease_store_can_renew_fenced_lease() -> None:
    store = InMemoryBillingJobLeaseStore()
    observed = datetime(2026, 4, 10, tzinfo=timezone.utc)
    first = create_job_lease(tenant_id='tenant-a', job_name='renewal', run_key='rk-renew', worker_id='worker-1', acquired_at=observed, lease_ttl=timedelta(minutes=5))
    saved = store.acquire(first)
    renewed = store.renew(tenant_id='tenant-a', job_name='renewal', run_key='rk-renew', fencing_token=saved.fencing_token, acquired_at=observed + timedelta(minutes=4, seconds=30), lease_ttl=timedelta(minutes=5))
    assert renewed.expires_at > saved.expires_at
    with pytest.raises(RuntimeError):
        store.renew(tenant_id='tenant-a', job_name='renewal', run_key='rk-renew', fencing_token='wrong', acquired_at=observed + timedelta(minutes=4, seconds=45), lease_ttl=timedelta(minutes=5))


def test_refund_and_chargeback_stamp_lineage_metadata(tmp_path: Path) -> None:
    from billing.refund_orchestrator import RefundOrchestrator
    from billing.chargeback_orchestrator import ChargebackOrchestrator
    from billing.payment_provider_contract import PaymentProviderContract
    from runtime.monetization import MonetizationService

    class _RefundProvider(PaymentProviderContract):
        def provider_name(self) -> str: return 'stripe'
        def ensure_customer(self, *, tenant_id: str, email: str | None = None, metadata=None): raise NotImplementedError
        def collect(self, attempt): raise NotImplementedError
        def refund(self, *, invoice_id: str, tenant_id: str, amount_minor: int, currency: str, reason: str, metadata=None):
            return {'refund_id': 'rf-1', 'external_reference': 'ext-rf-1', 'provider_name': 'stripe'}

    invoice = CommercialInvoiceEnvelope(tenant_id='tenant-a', invoice_id='inv-l1', currency='USD', subtotal_minor=100, tax_minor=0, total_minor=100, status=__import__('billing.commercial_cycle_contract', fromlist=['InvoiceLifecycleStatus']).InvoiceLifecycleStatus.PAID, issued_at=datetime(2026,4,10,tzinfo=timezone.utc), paid_minor=100, metadata={'provider_name_hint': 'stripe'})
    ledger = SqliteLedgerStore(sqlite_path=str(tmp_path / 'ledger.sqlite3'))
    refund_orch = RefundOrchestrator(provider=_RefundProvider(), ledger_store=ledger, monetization_service=MonetizationService(), refund_store=SqliteRefundStore(sqlite_path=str(tmp_path / 'refunds.sqlite3')) )
    updated_invoice, refund_result, _, _ = refund_orch.refund(invoice=invoice, user_id='u1', amount_minor=10, reason='goodwill', idempotency_key='idem-r1')
    assert refund_result.metadata['billing_lineage_root'] == 'billing:invoice:inv-l1'
    assert updated_invoice.metadata['last_recovery_event_type'] == 'refund'
    cb_orch = ChargebackOrchestrator(ledger_store=ledger, monetization_service=MonetizationService(), case_store=SqliteChargebackStore(sqlite_path=str(tmp_path / 'chargebacks.sqlite3')))
    cb_invoice, case, _, _ = cb_orch.open_case(invoice=invoice, user_id='u1', amount_minor=10, reason='fraud', idempotency_key='idem-c1')
    assert case.metadata['billing_lineage_root'] == 'billing:invoice:inv-l1'
    assert cb_invoice.metadata['last_recovery_event_type'] == 'chargeback'
