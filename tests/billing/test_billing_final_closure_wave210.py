from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import billing.scheduler.jobs as scheduler_jobs_module
from billing.commercial_cycle_contract import InvoiceLifecycleStatus
from billing.dunning_orchestrator import DunningOrchestrator
from billing.invoice_lifecycle import CommercialInvoiceEnvelope
from billing.reconciliation_service import BillingReconciliationService
from billing.scheduler import (
    DunningRetryJob,
    InMemoryBillingJobLeaseStore,
    ReconciliationJob,
    RenewalJob,
    SqliteBillingJobLeaseStore,
    SqliteBillingJobRunStore,
    create_job_lease,
)
from billing.sqlite_store import SqliteLedgerStore
from billing.subscription_lifecycle import (
    BillingCycleWindow,
    SubscriptionCommercialEnvelope,
    SubscriptionLifecycleStatus,
)
from billing.usage_rollup import UsageRollup
from observability.tenant_metrics_registry import TenantMetricsRegistry


class _RecordingLeaseStore(InMemoryBillingJobLeaseStore):
    def __init__(self) -> None:
        super().__init__()
        self.renew_calls = 0

    def renew(self, *, tenant_id: str, job_name: str, run_key: str, fencing_token: str, acquired_at: datetime, lease_ttl: timedelta):
        self.renew_calls += 1
        return super().renew(
            tenant_id=tenant_id,
            job_name=job_name,
            run_key=run_key,
            fencing_token=fencing_token,
            acquired_at=acquired_at,
            lease_ttl=lease_ttl,
        )


def _subscription(*, tenant_id: str, subscription_id: str, cycle_end: datetime) -> SubscriptionCommercialEnvelope:
    return SubscriptionCommercialEnvelope(
        tenant_id=tenant_id,
        subscription_id=subscription_id,
        plan_id='plan-pro',
        status=SubscriptionLifecycleStatus.ACTIVE,
        cycle=BillingCycleWindow(start_at=cycle_end - timedelta(days=30), end_at=cycle_end, anchor='monthly'),
    )


def _issued_invoice(*, tenant_id: str, invoice_id: str, total_minor: int, currency: str = 'USD') -> CommercialInvoiceEnvelope:
    return CommercialInvoiceEnvelope(
        tenant_id=tenant_id,
        invoice_id=invoice_id,
        subscription_id='sub-1',
        currency=currency,
        subtotal_minor=total_minor - 100,
        tax_minor=100,
        total_minor=total_minor,
        status=InvoiceLifecycleStatus.ISSUED,
        issued_at=datetime(2026, 4, 10, tzinfo=UTC),
    )


def test_multi_worker_contention_blocks_second_worker_until_stale_lease_expires(tmp_path: Path) -> None:
    observed = datetime(2026, 4, 10, 12, 0, tzinfo=UTC)
    orchestrator = DunningOrchestrator(metrics=TenantMetricsRegistry())
    orchestrator.open_run(tenant_id='tenant-a', invoice_id='inv-contention', started_at=observed - timedelta(days=10))

    run_store_path = str(tmp_path / 'job-runs.sqlite3')
    lease_store = SqliteBillingJobLeaseStore(sqlite_path=str(tmp_path / 'job-leases.sqlite3'))
    blocking = lease_store.acquire(
        create_job_lease(
            tenant_id='tenant-a',
            job_name='dunning_retry',
            run_key='rk-contention',
            worker_id='worker-1',
            acquired_at=observed,
            lease_ttl=timedelta(minutes=5),
        )
    )
    worker_two = DunningRetryJob(
        orchestrator=orchestrator,
        run_store=SqliteBillingJobRunStore(sqlite_path=run_store_path),
        lease_store=lease_store,
        worker_id='worker-2',
    )

    with pytest.raises(RuntimeError, match='already held'):
        worker_two.run(tenant_id='tenant-a', invoice_id='inv-contention', now=observed + timedelta(minutes=1), run_key='rk-contention')

    assert lease_store.release(
        tenant_id='tenant-a',
        job_name='dunning_retry',
        run_key='rk-contention',
        fencing_token=blocking.fencing_token,
    ) is True

    executed = worker_two.run(tenant_id='tenant-a', invoice_id='inv-contention', now=observed + timedelta(minutes=6), run_key='rk-contention')
    replayed = DunningRetryJob(
        orchestrator=orchestrator,
        run_store=SqliteBillingJobRunStore(sqlite_path=run_store_path),
        lease_store=lease_store,
        worker_id='worker-3',
    ).run(tenant_id='tenant-a', invoice_id='inv-contention', now=observed + timedelta(minutes=7), run_key='rk-contention')

    assert executed == (1, 2, 3)
    assert replayed == (1, 2, 3)


def test_long_running_renewal_job_renews_lease_before_expiry(monkeypatch) -> None:
    observed = datetime(2026, 4, 10, 12, 0, tzinfo=UTC)
    lease_store = _RecordingLeaseStore()
    job = RenewalJob(lease_store=lease_store, lease_ttl=timedelta(minutes=2), worker_id='worker-renew')
    subscriptions = (
        _subscription(tenant_id='tenant-a', subscription_id='sub-1', cycle_end=observed - timedelta(days=1)),
        _subscription(tenant_id='tenant-a', subscription_id='sub-2', cycle_end=observed - timedelta(days=2)),
        _subscription(tenant_id='tenant-a', subscription_id='sub-3', cycle_end=observed - timedelta(days=3)),
    )
    tick_values = iter((
        observed,
        observed + timedelta(minutes=1, seconds=30),
        observed + timedelta(minutes=1, seconds=31),
        observed + timedelta(minutes=1, seconds=32),
    ))
    monkeypatch.setattr(scheduler_jobs_module, 'utc_now', lambda: next(tick_values, observed + timedelta(minutes=1, seconds=32)))

    renewed = job.run(tenant_id='tenant-a', subscriptions=subscriptions, now=observed, run_key='rk-renew-long')

    assert len(renewed) == 3
    assert lease_store.renew_calls >= 1
    assert lease_store.get(tenant_id='tenant-a', job_name='renewal', run_key='rk-renew-long') is None


def test_reconciliation_replay_returns_original_report_after_underlying_ledger_changes(tmp_path: Path) -> None:
    now = datetime(2026, 4, 10, 12, 0, tzinfo=UTC)
    metrics = TenantMetricsRegistry()
    ledger = SqliteLedgerStore(sqlite_path=str(tmp_path / 'ledger.sqlite3'))
    run_store = SqliteBillingJobRunStore(sqlite_path=str(tmp_path / 'job-runs.sqlite3'))

    invoice = _issued_invoice(tenant_id='tenant-a', invoice_id='inv-chaos-a', total_minor=1000)
    usage = UsageRollup(tenant_id='tenant-a', meter_key='api.calls', window_key='2026-04', quantity=10.0)
    service = BillingReconciliationService(ledger_store=ledger, metrics=metrics)
    job = ReconciliationJob(service=service, run_store=run_store)

    first_report = job.run(
        tenant_id='tenant-a',
        invoices=(invoice,),
        usage_rollups=(usage,),
        now=now,
        run_key='rk-chaos-recon',
        usage_rate_minor_by_meter={'api.calls': 100},
    )
    assert sorted(d.drift_key for d in first_report.drifts) == ['invoice_vs_ledger', 'net_invoice_vs_ledger', 'usage_proxy_vs_ledger']

    from billing.ledger_event import LedgerEntry, LedgerPosting
    ledger.append(
        LedgerPosting(
            posting_id='p-chaos-1',
            tenant_id='tenant-a',
            reference_type='invoice',
            reference_id='inv-chaos-a',
            entries=(
                LedgerEntry(tenant_id='tenant-a', entry_id='d-chaos-1', account_code='billing.accounts.ar', side='debit', amount_minor=1000, currency='USD', reference_type='invoice', reference_id='inv-chaos-a'),
                LedgerEntry(tenant_id='tenant-a', entry_id='c-chaos-1', account_code='billing.accounts.revenue', side='credit', amount_minor=1000, currency='USD', reference_type='invoice', reference_id='inv-chaos-a'),
            ),
        )
    )

    replay_report = ReconciliationJob(
        service=BillingReconciliationService(ledger_store=ledger, metrics=metrics),
        run_store=SqliteBillingJobRunStore(sqlite_path=str(tmp_path / 'job-runs.sqlite3')),
    ).run(
        tenant_id='tenant-a',
        invoices=(invoice,),
        usage_rollups=(usage,),
        now=now + timedelta(minutes=3),
        run_key='rk-chaos-recon',
        usage_rate_minor_by_meter={'api.calls': 100},
    )

    assert replay_report == first_report
    assert metrics.snapshot(tenant_id='tenant-a')['billing_reconciliation_drift_count']['value'] == float(len(first_report.drifts))
