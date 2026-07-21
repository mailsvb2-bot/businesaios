from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
import hashlib
import json
from threading import RLock
from typing import Any, Protocol

from billing.commercial_cycle_contract import (
    ReconciliationDrift,
    require_aware_datetime,
    require_commercial_int,
    utc_now,
)
from billing.dunning_orchestrator import DunningOrchestrator
from billing.invoice_lifecycle import CommercialInvoiceEnvelope, InvoiceLifecycleService
from billing.reconciliation_service import BillingReconciliationService, ReconciliationReport
from billing.subscription_lifecycle import SubscriptionCommercialEnvelope, SubscriptionLifecycleService
from billing.usage_rollup import UsageRollup
from billing.scheduler.lease import BillingJobLeaseStoreContract, InMemoryBillingJobLeaseStore, SqliteBillingJobLeaseStore, create_job_lease
from core.tenancy.normalization import require_tenant_id
from runtime.platform.billing_scheduler_job_store import (
    CANON_PLATFORM_BILLING_SCHEDULER_JOB_STORE,
    PlatformSqliteBillingJobRunStore,
    SCHEMA_VERSION,
    canonical_json_snapshot,
)


CANON_BILLING_SCHEDULER_JOBS = True


def _require_text(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    return value.strip()


def _require_tenant_text(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("tenant_id must be a string")
    return require_tenant_id(value)


def _require_run_key(value: Any, *, default: str) -> str:
    candidate = default if value is None else value
    return _require_text("run_key", candidate)


def _require_fingerprint(name: str, value: Any) -> str:
    return _require_text(name, value)


def _require_attempts(payload: object) -> tuple[int, ...]:
    if not isinstance(payload, (list, tuple)):
        raise ValueError("executed_attempts must be a list or tuple")
    attempts = tuple(require_commercial_int("attempt_no", item, minimum=1) for item in payload)
    if len(set(attempts)) != len(attempts):
        raise ValueError("executed_attempts must not contain duplicates")
    return attempts


@dataclass(frozen=True)
class BillingJobRun:
    tenant_id: str
    job_name: str
    run_key: str
    started_at: datetime = field(default_factory=utc_now)
    finished_at: datetime | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        _require_tenant_text(self.tenant_id)
        _require_text("job_name", self.job_name)
        _require_text("run_key", self.run_key)
        require_aware_datetime("started_at", self.started_at)
        if self.finished_at is not None:
            require_aware_datetime("finished_at", self.finished_at)
            if self.finished_at < self.started_at:
                raise ValueError("finished_at must be >= started_at")
        if not isinstance(self.metadata, Mapping):
            raise ValueError("metadata must be a mapping")
        canonical_json_snapshot(self.metadata)

    def normalized_copy(self) -> BillingJobRun:
        self.validate()
        return replace(
            self,
            tenant_id=_require_tenant_text(self.tenant_id),
            job_name=_require_text("job_name", self.job_name),
            run_key=_require_text("run_key", self.run_key),
            metadata=canonical_json_snapshot(self.metadata),
        )


class BillingJobRunStoreContract(Protocol):
    def save(self, run: BillingJobRun) -> BillingJobRun: ...
    def get(self, *, tenant_id: str, job_name: str, run_key: str) -> BillingJobRun | None: ...


class InMemoryBillingJobRunStore:
    def __init__(self) -> None:
        self._runs: dict[tuple[str, str, str], BillingJobRun] = {}
        self._lock = RLock()

    def save(self, run: BillingJobRun) -> BillingJobRun:
        normalized = run.normalized_copy()
        key = (normalized.tenant_id, normalized.job_name, normalized.run_key)
        with self._lock:
            existing = self._runs.get(key)
            if existing is not None and existing != normalized:
                raise ValueError("billing job run collision")
            self._runs[key] = normalized
        return run

    def get(self, *, tenant_id: str, job_name: str, run_key: str) -> BillingJobRun | None:
        key = (
            _require_tenant_text(tenant_id),
            _require_text("job_name", job_name),
            _require_text("run_key", run_key),
        )
        with self._lock:
            run = self._runs.get(key)
            return None if run is None else run.normalized_copy()


class SqliteBillingJobRunStore(PlatformSqliteBillingJobRunStore):
    """Billing scheduler-facing job run store facade.

    SQLite ownership lives in runtime.platform.billing_scheduler_job_store.
    """

    def __init__(self, *, sqlite_path: str) -> None:
        super().__init__(sqlite_path=sqlite_path, run_cls=BillingJobRun)


def _stable_job_fingerprint(payload: object) -> str:
    canonical = canonical_json_snapshot(payload)
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _assert_replay_safe(
    existing: BillingJobRun,
    *,
    expected_fingerprint: str,
    accepted_fingerprints: tuple[str, ...] = (),
) -> None:
    existing = existing.normalized_copy()
    expected = _require_fingerprint("expected_fingerprint", expected_fingerprint)
    if not isinstance(accepted_fingerprints, tuple):
        raise ValueError("accepted_fingerprints must be a tuple")
    allowed = {expected}
    for item in accepted_fingerprints:
        allowed.add(_require_fingerprint("accepted_fingerprint", item))
    metadata = canonical_json_snapshot(existing.metadata)
    actual = metadata.get("input_fingerprint")
    result = metadata.get("result_fingerprint")
    if actual in allowed or result in allowed:
        return
    raise ValueError("billing job replay input mismatch for existing run_key")


def _serialize_reconciliation_report(report: ReconciliationReport) -> tuple[dict[str, object], ...]:
    tenant_id = _require_tenant_text(report.tenant_id)
    if not isinstance(report.drifts, tuple):
        raise ValueError("report.drifts must be a tuple")
    serialized: list[dict[str, object]] = []
    for drift in report.drifts:
        if not isinstance(drift, ReconciliationDrift):
            raise ValueError("report.drifts must contain ReconciliationDrift values")
        drift.validate()
        if drift.tenant_id != tenant_id:
            raise ValueError("reconciliation drift tenant mismatch")
        serialized.append(
            {
                "tenant_id": tenant_id,
                "drift_key": _require_text("drift_key", drift.drift_key),
                "expected_minor": require_commercial_int("expected_minor", drift.expected_minor),
                "observed_minor": require_commercial_int("observed_minor", drift.observed_minor),
                "delta_minor": require_commercial_int("delta_minor", drift.delta_minor),
                "severity": _require_text("severity", drift.severity),
                "details": canonical_json_snapshot(drift.details),
            }
        )
    return tuple(serialized)


def _deserialize_reconciliation_report(*, tenant_id: str, payload: object) -> ReconciliationReport | None:
    tid = _require_tenant_text(tenant_id)
    if not isinstance(payload, (list, tuple)):
        return None
    drifts: list[ReconciliationDrift] = []
    for item in payload:
        if not isinstance(item, Mapping):
            return None
        item_tenant = item.get("tenant_id", tid)
        drift_tid = _require_tenant_text(item_tenant)
        if drift_tid != tid:
            raise ValueError("reconciliation drift tenant mismatch")
        details = item.get("details", {})
        if not isinstance(details, Mapping):
            raise ValueError("reconciliation drift details must be a mapping")
        drift = ReconciliationDrift(
            tenant_id=tid,
            drift_key=_require_text("drift_key", item.get("drift_key")),
            expected_minor=require_commercial_int("expected_minor", item.get("expected_minor")),
            observed_minor=require_commercial_int("observed_minor", item.get("observed_minor")),
            delta_minor=require_commercial_int("delta_minor", item.get("delta_minor")),
            severity=_require_text("severity", item.get("severity")),
            details=canonical_json_snapshot(details),
        )
        drift.validate()
        drifts.append(drift)
    return ReconciliationReport(tenant_id=tid, drifts=tuple(drifts))


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
        tid = _require_tenant_text(tenant_id)
        observed_at = now or utc_now()
        if observed_at.tzinfo is None:
            raise ValueError('now must be timezone-aware')
        subscriptions_tuple = tuple(subscriptions)
        fingerprint = _stable_job_fingerprint([(sub.subscription_id, sub.status.value, sub.cycle.start_at.isoformat(), sub.cycle.end_at.isoformat(), sub.plan_id, dict(sub.metadata)) for sub in subscriptions_tuple if sub.tenant_id == tid])
        normalized_run_key = _require_run_key(run_key, default=observed_at.date().isoformat())
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
        tid = _require_tenant_text(tenant_id)
        observed_at = issued_at or utc_now()
        if observed_at.tzinfo is None:
            raise ValueError('issued_at must be timezone-aware')
        if due_at is not None and due_at.tzinfo is None:
            raise ValueError('due_at must be timezone-aware')
        invoices_tuple = tuple(invoices)
        fingerprint = _stable_job_fingerprint([(inv.invoice_id, inv.status.value, inv.total_minor, inv.paid_minor, dict(inv.metadata)) for inv in invoices_tuple if inv.tenant_id == tid])
        normalized_run_key = _require_run_key(run_key, default=observed_at.isoformat())
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
        tid = _require_tenant_text(tenant_id)
        iid = _require_text("invoice_id", invoice_id)
        observed_at = now or utc_now()
        if observed_at.tzinfo is None:
            raise ValueError('now must be timezone-aware')
        normalized_run_key = _require_run_key(run_key, default=f"{iid}:{observed_at.isoformat()}")
        with _job_lease_context(lease_store=self._lease_store, tenant_id=tid, job_name='dunning_retry', run_key=normalized_run_key, worker_id=self._worker_id, observed_at=observed_at, lease_ttl=self._lease_ttl) as lease_holder:
            fingerprint = _stable_job_fingerprint({"invoice_id": iid})
            existing_run = self._run_store.get(tenant_id=tid, job_name="dunning_retry", run_key=normalized_run_key)
            if existing_run is not None:
                metadata = canonical_json_snapshot(existing_run.metadata)
                stored_fingerprint = metadata.get("input_fingerprint")
                if stored_fingerprint is not None:
                    _assert_replay_safe(existing_run, expected_fingerprint=fingerprint)
                elif metadata.get("invoice_id") != iid:
                    raise ValueError("billing job replay input mismatch for existing run_key")
                return _require_attempts(metadata.get("executed_attempts", ()))
            due_actions = self._orchestrator.due_actions(tenant_id=tid, invoice_id=iid, now=observed_at)
            executed_attempts: list[int] = []
            for action in due_actions:
                _renew_lease_if_due(lease_store=self._lease_store, holder=lease_holder, tenant_id=tid, job_name='dunning_retry', run_key=normalized_run_key, lease_ttl=self._lease_ttl, now=observed_at)
                self._orchestrator.mark_action_executed(tenant_id=tid, invoice_id=iid, attempt_no=action.attempt_no)
                executed_attempts.append(int(action.attempt_no))
            result_attempts = tuple(executed_attempts)
            self._run_store.save(
                BillingJobRun(
                    tenant_id=tid,
                    job_name="dunning_retry",
                    run_key=normalized_run_key,
                    started_at=observed_at,
                    finished_at=observed_at,
                    metadata={
                        "owner": "billing.scheduler.jobs",
                        "invoice_id": iid,
                        "input_fingerprint": fingerprint,
                        "result_fingerprint": _stable_job_fingerprint(result_attempts),
                        "executed_attempts": result_attempts,
                    },
                )
            )
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
        tid = _require_tenant_text(tenant_id)
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
        normalized_run_key = _require_run_key(run_key, default=observed_at.isoformat())
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
