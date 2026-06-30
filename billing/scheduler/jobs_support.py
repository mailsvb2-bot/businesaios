from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import sqlite3
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


CANON_BILLING_SCHEDULER_JOBS = True
SCHEMA_VERSION = 1


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


class SqliteBillingJobRunStore:
    def __init__(self, *, sqlite_path: str) -> None:
        self._path = str(sqlite_path).strip()
        if not self._path:
            raise ValueError('sqlite_path is required')
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._path)
        conn.execute('PRAGMA foreign_keys = ON')
        conn.execute('PRAGMA journal_mode = WAL')
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS billing_schema_version (component TEXT PRIMARY KEY, version INTEGER NOT NULL)')
            row = conn.execute('SELECT version FROM billing_schema_version WHERE component = ?', ('job_runs',)).fetchone()
            if row is None:
                conn.execute('INSERT INTO billing_schema_version(component, version) VALUES (?, ?)', ('job_runs', SCHEMA_VERSION))
            elif int(row[0]) != SCHEMA_VERSION:
                raise RuntimeError('unsupported job_runs schema version')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS billing_job_runs (
                    tenant_id TEXT NOT NULL,
                    job_name TEXT NOT NULL,
                    run_key TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, job_name, run_key)
                )
            ''')

    def save(self, run: BillingJobRun) -> BillingJobRun:
        run.validate()
        tid = require_tenant_id(run.tenant_id)
        job_name = str(run.job_name).strip()
        run_key = str(run.run_key).strip()
        payload = {
            'tenant_id': run.tenant_id,
            'job_name': job_name,
            'run_key': run_key,
            'started_at': run.started_at.isoformat(),
            'finished_at': None if run.finished_at is None else run.finished_at.isoformat(),
            'metadata': dict(run.metadata),
        }
        with self._connect() as conn:
            row = conn.execute('SELECT payload_json FROM billing_job_runs WHERE tenant_id = ? AND job_name = ? AND run_key = ?', (tid, job_name, run_key)).fetchone()
            if row is not None:
                existing = self._decode(row[0])
                if existing != run:
                    raise ValueError('billing job run collision')
                return existing
            conn.execute('INSERT INTO billing_job_runs(tenant_id, job_name, run_key, payload_json) VALUES (?, ?, ?, ?)', (tid, job_name, run_key, json.dumps(payload, sort_keys=True)))
        return run

    def get(self, *, tenant_id: str, job_name: str, run_key: str) -> BillingJobRun | None:
        tid = require_tenant_id(tenant_id)
        normalized_job = str(job_name).strip()
        normalized_key = str(run_key).strip()
        if not normalized_job or not normalized_key:
            raise ValueError('job_name and run_key are required')
        with self._connect() as conn:
            row = conn.execute('SELECT payload_json FROM billing_job_runs WHERE tenant_id = ? AND job_name = ? AND run_key = ?', (tid, normalized_job, normalized_key)).fetchone()
        return None if row is None else self._decode(row[0])

    def _decode(self, payload_json: str) -> BillingJobRun:
        payload = json.loads(payload_json)
        payload['started_at'] = datetime.fromisoformat(payload['started_at'])
        if payload['finished_at'] is not None:
            payload['finished_at'] = datetime.fromisoformat(payload['finished_at'])
        run = BillingJobRun(**payload)
        run.validate()
        return run


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



__all__ = [
    'CANON_BILLING_SCHEDULER_JOBS',
    'SCHEMA_VERSION',
    'BillingJobRun',
    'BillingJobRunStoreContract',
    'InMemoryBillingJobRunStore',
    'SqliteBillingJobRunStore',
    '_stable_job_fingerprint',
    '_assert_replay_safe',
    '_serialize_reconciliation_report',
    '_deserialize_reconciliation_report',
    '_job_lease_context',
    '_renew_lease_if_due',
]
