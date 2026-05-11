from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import hashlib
import json
from typing import Iterable, Iterator, Mapping, Protocol

from billing.commercial_cycle_contract import utc_now
from billing.dunning_orchestrator import DunningOrchestrator
from billing.invoice_lifecycle import CommercialInvoiceEnvelope, InvoiceLifecycleService
from billing.reconciliation_service import BillingReconciliationService, ReconciliationReport
from billing.commercial_cycle_contract import ReconciliationDrift
from billing.subscription_lifecycle import SubscriptionCommercialEnvelope, SubscriptionLifecycleService
from billing.usage_rollup import UsageRollup
from billing.scheduler.lease import BillingJobLeaseStoreContract, InMemoryBillingJobLeaseStore, SqliteBillingJobLeaseStore, create_job_lease
from core.tenancy.normalization import require_tenant_id
from runtime.platform.billing_scheduler_job_store import (
    CANON_PLATFORM_BILLING_SCHEDULER_JOB_STORE,
    PlatformSqliteBillingJobRunStore,
    SCHEMA_VERSION,
)


CANON_BILLING_SCHEDULER_JOBS = True


@dataclass(frozen=True)
class BillingJobRun:
    tenant_id: str
    job_name: str
    run_key: str
    started_at: datetime = field(default_factory=utc_now)
    finished_at: datetime | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if not str(self.job_name or '').strip():
            raise ValueError('job_name is required')
        if not str(self.run_key or '').strip():
            raise ValueError('run_key is required')
        if self.started_at.tzinfo is None:
            raise ValueError('started_at must be timezone-aware')
        if self.finished_at is not None and self.finished_at.tzinfo is None:
            raise ValueError('finished_at must be timezone-aware')
        if self.finished_at is not None and self.finished_at < self.started_at:
            raise ValueError('finished_at must be >= started_at')


class BillingJobRunStoreContract(Protocol):
    def save(self, run: BillingJobRun) -> BillingJobRun: ...
    def get(self, *, tenant_id: str, job_name: str, run_key: str) -> BillingJobRun | None: ...


class InMemoryBillingJobRunStore:
    def __init__(self) -> None:
        self._runs: dict[tuple[str, str, str], BillingJobRun] = {}

    def save(self, run: BillingJobRun) -> BillingJobRun:
        run.validate()
        key = (run.tenant_id, run.job_name, run.run_key)
        existing = self._runs.get(key)
        if existing is not None and existing != run:
            raise ValueError('billing job run collision')
        self._runs[key] = run
        return run

    def get(self, *, tenant_id: str, job_name: str, run_key: str) -> BillingJobRun | None:
        return self._runs.get((require_tenant_id(tenant_id), str(job_name).strip(), str(run_key).strip()))


class SqliteBillingJobRunStore(PlatformSqliteBillingJobRunStore):
    """Billing scheduler-facing job run store facade.

    SQLite ownership lives in runtime.platform.billing_scheduler_job_store.
    """

    def __init__(self, *, sqlite_path: str) -> None:
        super().__init__(sqlite_path=sqlite_path, run_cls=BillingJobRun)


def _stable_job_fingerprint(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'), default=str).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def _assert_replay_safe(existing: BillingJobRun, *, expected_fingerprint: str, accepted_fingerprints: tuple[str, ...] = ()) -> None:
    actual = str(dict(existing.metadata).get('input_fingerprint') or '')
    allowed = {item for item in (expected_fingerprint, *accepted_fingerprints) if item}
    if actual and actual not in allowed:
        result_fingerprint = str(dict(existing.metadata).get('result_fingerprint') or '')
        if not result_fingerprint or result_fingerprint not in allowed:
            raise ValueError('billing job replay input mismatch for existing run_key')


def _serialize_reconciliation_report(report: ReconciliationReport) -> tuple[dict[str, object], ...]:
    serialized: list[dict[str, object]] = []
    for drift in report.drifts:
        serialized.append({
            'tenant_id': drift.tenant_id,
            'drift_key': drift.drift_key,
            'expected_minor': int(drift.expected_minor),
            'observed_minor': int(drift.observed_minor),
            'delta_minor': int(drift.delta_minor),
            'severity': str(drift.severity),
            'details': dict(drift.details),
        })
    return tuple(serialized)


def _deserialize_reconciliation_report(*, tenant_id: str, payload: object) -> ReconciliationReport | None:
    if not isinstance(payload, (list, tuple)):
        return None
    drifts: list[ReconciliationDrift] = []
    for item in payload:
        if not isinstance(item, dict):
            return None
        drift = ReconciliationDrift(
            tenant_id=str(item.get('tenant_id') or tenant_id),
            drift_key=str(item.get('drift_key') or ''),
            expected_minor=int(item.get('expected_minor') or 0),
            observed_minor=int(item.get('observed_minor') or 0),
            delta_minor=int(item.get('delta_minor') or 0),
            severity=str(item.get('severity') or ''),
            details=dict(item.get('details') or {}),
        )
        drift.validate()
        drifts.append(drift)
    return ReconciliationReport(tenant_id=tenant_id, drifts=tuple(drifts))


@contextmanager
def _job_lease_context(*, lease_store: BillingJobLeaseStoreContract | None, tenant_id: str, job_name: str, run_key: str, worker_id: str, observed_at: datetime, lease_ttl: timedelta) -> Iterator[dict[str, object]]:
    if lease_store is None:
        yield {'lease': None}
        return
    lease = create_job_lease(
        tenant_id=tenant_id,
        job_name=job_name,
        run_key=run_key,
        worker_id=worker_id,
        acquired_at=observed_at,
        lease_ttl=lease_ttl,
        metadata={'owner': 'billing.scheduler.jobs'},
    )
    acquired = lease_store.acquire(lease)
    holder = {'lease': acquired}
    try:
        yield holder
    finally:
        current = holder.get('lease') or acquired
        lease_store.release(tenant_id=tenant_id, job_name=job_name, run_key=run_key, fencing_token=current.fencing_token)


def _renew_lease_if_due(*, lease_store: BillingJobLeaseStoreContract | None, holder: dict[str, object], tenant_id: str, job_name: str, run_key: str, lease_ttl: timedelta, now: datetime | None = None, threshold: timedelta = timedelta(minutes=1)) -> None:
    if lease_store is None:
        return
    lease = holder.get('lease')
    if lease is None or lease.expires_at is None:
        return
    renewal_observed_at = now or utc_now()
    if renewal_observed_at.tzinfo is None:
        raise ValueError('now must be timezone-aware')
    if renewal_observed_at < lease.expires_at - threshold:
        return
    holder['lease'] = lease_store.renew(tenant_id=tenant_id, job_name=job_name, run_key=run_key, fencing_token=lease.fencing_token, acquired_at=renewal_observed_at, lease_ttl=lease_ttl)


class RenewalJob:
    def __init__(self, *, lifecycle: SubscriptionLifecycleService | None = None, run_store: BillingJobRunStoreContract | None = None, lease_store: BillingJobLeaseStoreContract | None = None, worker_id: str = 'billing-worker', lease_ttl: timedelta = timedelta(minutes=5)) -> None:
        self._lifecycle = lifecycle or SubscriptionLifecycleService()
        self._run_store = run_store or InMemoryBillingJobRunStore()
        self._lease_store = lease_store
        self._worker_id = str(worker_id).strip() or 'billing-worker'
        if lease_ttl.total_seconds() <= 0:
            raise ValueError('lease_ttl must be > 0')
        self._lease_ttl = lease_ttl

    def run(
        self,
        *,
        tenant_id: str,
        subscriptions: Iterable[SubscriptionCommercialEnvelope],
        now: datetime | None = None,
        run_key: str | None = None,
    ) -> tuple[SubscriptionCommercialEnvelope, ...]:
        tid = require_tenant_id(tenant_id)
        observed_at = now or utc_now()
        if observed_at.tzinfo is None:
            raise ValueError('now must be timezone-aware')
        subscriptions_tuple = tuple(subscriptions)
        fingerprint = _stable_job_fingerprint([(sub.subscription_id, sub.status.value, sub.cycle.start_at.isoformat(), sub.cycle.end_at.isoformat(), sub.plan_id, dict(sub.metadata)) for sub in subscriptions_tuple if sub.tenant_id == tid])
        normalized_run_key = str(run_key or observed_at.date().isoformat()).strip()
        with _job_lease_context(lease_store=self._lease_store, tenant_id=tid, job_name='renewal', run_key=normalized_run_key, worker_id=self._worker_id, observed_at=observed_at, lease_ttl=self._lease_ttl) as lease_holder:
            existing_run = self._run_store.get(tenant_id=tid, job_name='renewal', run_key=normalized_run_key)
            replay_mode = existing_run is not None
            if existing_run is not None:
                _assert_replay_safe(existing_run, expected_fingerprint=fingerprint)
                observed_at = existing_run.started_at

            updated: list[SubscriptionCommercialEnvelope] = []
            for subscription in subscriptions_tuple:
                _renew_lease_if_due(lease_store=self._lease_store, holder=lease_holder, tenant_id=tid, job_name='renewal', run_key=normalized_run_key, lease_ttl=self._lease_ttl, now=utc_now())
                subscription.validate()
                if subscription.tenant_id != tid:
                    continue
                current = self._lifecycle.advance_trial(subscription, now=observed_at)
                current = self._lifecycle.suspend_if_expired(current, now=observed_at)
                if current.status.value in {'active', 'trialing'} and observed_at >= current.cycle.end_at:
                    current = self._lifecycle.renew_cycle(current, now=observed_at)
                updated.append(current)
            result_fingerprint = _stable_job_fingerprint([(sub.subscription_id, sub.status.value, sub.cycle.start_at.isoformat(), sub.cycle.end_at.isoformat(), sub.plan_id, dict(sub.metadata)) for sub in updated])
            if not replay_mode:
                self._run_store.save(BillingJobRun(tenant_id=tid, job_name='renewal', run_key=normalized_run_key, started_at=observed_at, finished_at=observed_at, metadata={'owner': 'billing.scheduler.jobs', 'input_fingerprint': fingerprint, 'result_fingerprint': result_fingerprint, 'result_subscription_ids': tuple(sub.subscription_id for sub in updated)}))
            return tuple(updated)


class InvoiceIssueJob:
    def __init__(self, *, lifecycle: InvoiceLifecycleService | None = None, run_store: BillingJobRunStoreContract | None = None, lease_store: BillingJobLeaseStoreContract | None = None, worker_id: str = 'billing-worker', lease_ttl: timedelta = timedelta(minutes=5)) -> None:
        self._lifecycle = lifecycle or InvoiceLifecycleService()
        self._run_store = run_store or InMemoryBillingJobRunStore()
        self._lease_store = lease_store
        self._worker_id = str(worker_id).strip() or 'billing-worker'
        if lease_ttl.total_seconds() <= 0:
            raise ValueError('lease_ttl must be > 0')
        self._lease_ttl = lease_ttl

    def run(
        self,
        *,
        tenant_id: str,
        invoices: Iterable[CommercialInvoiceEnvelope],
        due_at: datetime | None = None,
        issued_at: datetime | None = None,
        run_key: str | None = None,
    ) -> tuple[CommercialInvoiceEnvelope, ...]:
        tid = require_tenant_id(tenant_id)
        observed_at = issued_at or utc_now()
        if observed_at.tzinfo is None:
            raise ValueError('issued_at must be timezone-aware')
        if due_at is not None and due_at.tzinfo is None:
            raise ValueError('due_at must be timezone-aware')
        invoices_tuple = tuple(invoices)
        fingerprint = _stable_job_fingerprint([(inv.invoice_id, inv.status.value, inv.total_minor, inv.paid_minor, dict(inv.metadata)) for inv in invoices_tuple if inv.tenant_id == tid])
        normalized_run_key = str(run_key or observed_at.isoformat()).strip()
        with _job_lease_context(lease_store=self._lease_store, tenant_id=tid, job_name='invoice_issue', run_key=normalized_run_key, worker_id=self._worker_id, observed_at=observed_at, lease_ttl=self._lease_ttl) as lease_holder:
            existing_run = self._run_store.get(tenant_id=tid, job_name='invoice_issue', run_key=normalized_run_key)
            replay_mode = existing_run is not None
            if existing_run is not None:
                _assert_replay_safe(existing_run, expected_fingerprint=fingerprint)
                observed_at = existing_run.started_at

            updated: list[CommercialInvoiceEnvelope] = []
            for invoice in invoices_tuple:
                _renew_lease_if_due(lease_store=self._lease_store, holder=lease_holder, tenant_id=tid, job_name='invoice_issue', run_key=normalized_run_key, lease_ttl=self._lease_ttl, now=utc_now())
                invoice.validate()
                if invoice.tenant_id != tid:
                    continue
                current = invoice
                if current.status.value == 'draft':
                    current = self._lifecycle.issue(current, issued_at=observed_at, due_at=due_at)
                updated.append(current)
            result_fingerprint = _stable_job_fingerprint([(inv.invoice_id, inv.status.value, inv.total_minor, inv.paid_minor, dict(inv.metadata)) for inv in updated])
            if not replay_mode:
                self._run_store.save(BillingJobRun(tenant_id=tid, job_name='invoice_issue', run_key=normalized_run_key, started_at=observed_at, finished_at=observed_at, metadata={'owner': 'billing.scheduler.jobs', 'input_fingerprint': fingerprint, 'result_fingerprint': result_fingerprint, 'result_invoice_ids': tuple(inv.invoice_id for inv in updated)}))
            return tuple(updated)


class DunningRetryJob:
    def __init__(self, *, orchestrator: DunningOrchestrator, run_store: BillingJobRunStoreContract | None = None, lease_store: BillingJobLeaseStoreContract | None = None, worker_id: str = 'billing-worker', lease_ttl: timedelta = timedelta(minutes=5)) -> None:
        self._orchestrator = orchestrator
        self._run_store = run_store or InMemoryBillingJobRunStore()
        self._lease_store = lease_store
        self._worker_id = str(worker_id).strip() or 'billing-worker'
        if lease_ttl.total_seconds() <= 0:
            raise ValueError('lease_ttl must be > 0')
        self._lease_ttl = lease_ttl

    def run(
        self,
        *,
        tenant_id: str,
        invoice_id: str,
        now: datetime | None = None,
        run_key: str | None = None,
    ) -> tuple[int, ...]:
        tid = require_tenant_id(tenant_id)
        iid = str(invoice_id).strip()
        if not iid:
            raise ValueError('invoice_id is required')
        observed_at = now or utc_now()
        if observed_at.tzinfo is None:
            raise ValueError('now must be timezone-aware')
        normalized_run_key = str(run_key or f"{iid}:{observed_at.isoformat()}").strip()
        with _job_lease_context(lease_store=self._lease_store, tenant_id=tid, job_name='dunning_retry', run_key=normalized_run_key, worker_id=self._worker_id, observed_at=observed_at, lease_ttl=self._lease_ttl) as lease_holder:
            existing_run = self._run_store.get(tenant_id=tid, job_name='dunning_retry', run_key=normalized_run_key)
            if existing_run is not None:
                return tuple(int(item) for item in dict(existing_run.metadata).get('executed_attempts', ()))
            due_actions = self._orchestrator.due_actions(tenant_id=tid, invoice_id=iid, now=observed_at)
            executed_attempts: list[int] = []
            for action in due_actions:
                _renew_lease_if_due(lease_store=self._lease_store, holder=lease_holder, tenant_id=tid, job_name='dunning_retry', run_key=normalized_run_key, lease_ttl=self._lease_ttl, now=observed_at)
                self._orchestrator.mark_action_executed(tenant_id=tid, invoice_id=iid, attempt_no=action.attempt_no)
                executed_attempts.append(int(action.attempt_no))
            self._run_store.save(BillingJobRun(tenant_id=tid, job_name='dunning_retry', run_key=normalized_run_key, started_at=observed_at, finished_at=observed_at, metadata={'owner': 'billing.scheduler.jobs', 'invoice_id': iid, 'executed_attempts': tuple(executed_attempts)}))
            return tuple(executed_attempts)


class ReconciliationJob:
    def __init__(self, *, service: BillingReconciliationService, run_store: BillingJobRunStoreContract | None = None, lease_store: BillingJobLeaseStoreContract | None = None, worker_id: str = 'billing-worker', lease_ttl: timedelta = timedelta(minutes=5)) -> None:
        self._service = service
        self._run_store = run_store or InMemoryBillingJobRunStore()
        self._lease_store = lease_store
        self._worker_id = str(worker_id).strip() or 'billing-worker'
        if lease_ttl.total_seconds() <= 0:
            raise ValueError('lease_ttl must be > 0')
        self._lease_ttl = lease_ttl

    def run(
        self,
        *,
        tenant_id: str,
        invoices: Iterable[CommercialInvoiceEnvelope],
        usage_rollups: Iterable[UsageRollup],
        now: datetime | None = None,
        run_key: str | None = None,
        revenue_account: str = 'billing.accounts.revenue',
        usage_rate_minor_by_meter: Mapping[str, int] | None = None,
    ) -> ReconciliationReport:
        tid = require_tenant_id(tenant_id)
        observed_at = now or utc_now()
        if observed_at.tzinfo is None:
            raise ValueError('now must be timezone-aware')
        invoices_tuple = tuple(invoices)
        usage_tuple = tuple(usage_rollups)
        fingerprint = _stable_job_fingerprint({
            'invoices': [(inv.invoice_id, inv.total_minor, inv.status.value, inv.paid_minor, dict(inv.metadata)) for inv in invoices_tuple if inv.tenant_id == tid],
            'usage': [(u.meter_key, u.window_key, u.quantity) for u in usage_tuple if u.tenant_id == tid],
            'revenue_account': revenue_account,
            'usage_rate_minor_by_meter': dict(usage_rate_minor_by_meter or {}),
        })
        normalized_run_key = str(run_key or observed_at.isoformat()).strip()
        with _job_lease_context(lease_store=self._lease_store, tenant_id=tid, job_name='reconciliation', run_key=normalized_run_key, worker_id=self._worker_id, observed_at=observed_at, lease_ttl=self._lease_ttl) as lease_holder:
            _renew_lease_if_due(lease_store=self._lease_store, holder=lease_holder, tenant_id=tid, job_name='reconciliation', run_key=normalized_run_key, lease_ttl=self._lease_ttl, now=observed_at)
            existing = self._run_store.get(tenant_id=tid, job_name='reconciliation', run_key=normalized_run_key)
            if existing is not None:
                _assert_replay_safe(existing, expected_fingerprint=fingerprint)
                replay_report = _deserialize_reconciliation_report(tenant_id=tid, payload=dict(existing.metadata).get('report_drifts'))
                if replay_report is not None:
                    return replay_report
                return self._service.reconcile(
                    tenant_id=tid,
                    invoices=invoices_tuple,
                    usage_rollups=usage_tuple,
                    revenue_account=revenue_account,
                    usage_rate_minor_by_meter=usage_rate_minor_by_meter,
                )
            report = self._service.reconcile(
                tenant_id=tid,
                invoices=invoices_tuple,
                usage_rollups=usage_tuple,
                revenue_account=revenue_account,
                usage_rate_minor_by_meter=usage_rate_minor_by_meter,
            )
            self._run_store.save(BillingJobRun(tenant_id=tid, job_name='reconciliation', run_key=normalized_run_key, started_at=observed_at, finished_at=observed_at, metadata={'owner': 'billing.scheduler.jobs', 'drift_count': len(report.drifts), 'input_fingerprint': fingerprint, 'report_drifts': _serialize_reconciliation_report(report)}))
            return report


__all__ = [
    'BillingJobRun',
    'CANON_BILLING_SCHEDULER_JOBS',
    'CANON_PLATFORM_BILLING_SCHEDULER_JOB_STORE',
    'BillingJobRunStoreContract',
    'DunningRetryJob',
    'BillingJobLeaseStoreContract',
    'InMemoryBillingJobLeaseStore',
    'create_job_lease',
    'InMemoryBillingJobRunStore',
    'InvoiceIssueJob',
    'ReconciliationJob',
    'RenewalJob',
    'SCHEMA_VERSION',
    'SqliteBillingJobRunStore',
    'SqliteBillingJobLeaseStore',
]
