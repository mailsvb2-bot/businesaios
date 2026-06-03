from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from collections.abc import Iterator

from core.tenancy.normalization import require_tenant_id

CANON_PLATFORM_BILLING_SCHEDULER_LEASE_STORE = True
LEASE_SCHEMA_VERSION = 1


class PlatformSqliteBillingJobLeaseStore:
    def __init__(self, *, sqlite_path: str, lease_cls: type, utc_now_fn: Any) -> None:
        self._path = str(sqlite_path).strip()
        self._lease_cls = lease_cls
        self._utc_now = utc_now_fn
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
            row = conn.execute('SELECT version FROM billing_schema_version WHERE component = ?', ('job_leases',)).fetchone()
            if row is None:
                conn.execute('INSERT INTO billing_schema_version(component, version) VALUES (?, ?)', ('job_leases', LEASE_SCHEMA_VERSION))
            elif int(row[0]) != LEASE_SCHEMA_VERSION:
                raise RuntimeError('unsupported job_leases schema version')
            conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS billing_job_leases (
                    tenant_id TEXT NOT NULL,
                    job_name TEXT NOT NULL,
                    run_key TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, job_name, run_key)
                )
                '''
            )

    def acquire(self, lease: Any) -> Any:
        lease.validate()
        tid = require_tenant_id(lease.tenant_id)
        job = str(lease.job_name).strip()
        run = str(lease.run_key).strip()
        payload = self._encode(lease)
        with self._connect() as conn:
            row = conn.execute(
                'SELECT payload_json FROM billing_job_leases WHERE tenant_id = ? AND job_name = ? AND run_key = ?',
                (tid, job, run),
            ).fetchone()
            if row is not None:
                existing = self._decode(row[0])
                if not self._is_expired(existing, now=lease.acquired_at):
                    raise RuntimeError('billing job lease already held')
                conn.execute(
                    'UPDATE billing_job_leases SET payload_json = ? WHERE tenant_id = ? AND job_name = ? AND run_key = ?',
                    (json.dumps(payload, sort_keys=True), tid, job, run),
                )
                return lease
            conn.execute(
                'INSERT INTO billing_job_leases(tenant_id, job_name, run_key, payload_json) VALUES (?, ?, ?, ?)',
                (tid, job, run, json.dumps(payload, sort_keys=True)),
            )
        return lease

    def get(self, *, tenant_id: str, job_name: str, run_key: str) -> Any | None:
        tid = require_tenant_id(tenant_id)
        job = str(job_name).strip()
        run = str(run_key).strip()
        if not job or not run:
            raise ValueError('job_name and run_key are required')
        with self._connect() as conn:
            row = conn.execute(
                'SELECT payload_json FROM billing_job_leases WHERE tenant_id = ? AND job_name = ? AND run_key = ?',
                (tid, job, run),
            ).fetchone()
            if row is None:
                return None
            lease = self._decode(row[0])
            if self._is_expired(lease, now=self._utc_now()):
                conn.execute(
                    'DELETE FROM billing_job_leases WHERE tenant_id = ? AND job_name = ? AND run_key = ?',
                    (tid, job, run),
                )
                return None
            return lease

    def renew(self, *, tenant_id: str, job_name: str, run_key: str, fencing_token: str, acquired_at: datetime, lease_ttl: timedelta) -> Any:
        tid = require_tenant_id(tenant_id)
        job = str(job_name).strip()
        run = str(run_key).strip()
        token = str(fencing_token).strip()
        if acquired_at.tzinfo is None:
            raise ValueError('acquired_at must be timezone-aware')
        if lease_ttl.total_seconds() <= 0:
            raise ValueError('lease_ttl must be > 0')
        if not job or not run or not token:
            raise ValueError('job_name, run_key, and fencing_token are required')
        with self._connect() as conn:
            row = conn.execute(
                'SELECT payload_json FROM billing_job_leases WHERE tenant_id = ? AND job_name = ? AND run_key = ?',
                (tid, job, run),
            ).fetchone()
            if row is None:
                raise LookupError('billing job lease not held')
            existing = self._decode(row[0])
            if self._is_expired(existing, now=acquired_at):
                raise LookupError('billing job lease not held')
            if str(existing.fencing_token) != token:
                raise RuntimeError('billing job lease fencing mismatch')
            renewed = self._lease_cls(
                tenant_id=existing.tenant_id,
                job_name=existing.job_name,
                run_key=existing.run_key,
                worker_id=existing.worker_id,
                fencing_token=existing.fencing_token,
                acquired_at=acquired_at,
                expires_at=acquired_at + lease_ttl,
                metadata=dict(existing.metadata),
            )
            renewed.validate()
            conn.execute(
                'UPDATE billing_job_leases SET payload_json = ? WHERE tenant_id = ? AND job_name = ? AND run_key = ?',
                (json.dumps(self._encode(renewed), sort_keys=True), tid, job, run),
            )
            return renewed

    def release(self, *, tenant_id: str, job_name: str, run_key: str, fencing_token: str) -> bool:
        tid = require_tenant_id(tenant_id)
        job = str(job_name).strip()
        run = str(run_key).strip()
        token = str(fencing_token).strip()
        if not job or not run or not token:
            raise ValueError('job_name, run_key, and fencing_token are required')
        with self._connect() as conn:
            row = conn.execute(
                'SELECT payload_json FROM billing_job_leases WHERE tenant_id = ? AND job_name = ? AND run_key = ?',
                (tid, job, run),
            ).fetchone()
            if row is None:
                return False
            lease = self._decode(row[0])
            if str(lease.fencing_token) != token:
                return False
            conn.execute(
                'DELETE FROM billing_job_leases WHERE tenant_id = ? AND job_name = ? AND run_key = ?',
                (tid, job, run),
            )
            return True

    @staticmethod
    def _is_expired(lease: Any, *, now: datetime) -> bool:
        return lease.expires_at is not None and now >= lease.expires_at

    @staticmethod
    def _encode(lease: Any) -> dict[str, object]:
        return {
            'tenant_id': lease.tenant_id,
            'job_name': lease.job_name,
            'run_key': lease.run_key,
            'worker_id': lease.worker_id,
            'fencing_token': lease.fencing_token,
            'acquired_at': lease.acquired_at.isoformat(),
            'expires_at': None if lease.expires_at is None else lease.expires_at.isoformat(),
            'metadata': dict(lease.metadata),
        }

    def _decode(self, payload_json: str) -> Any:
        payload = json.loads(payload_json)
        payload['acquired_at'] = datetime.fromisoformat(payload['acquired_at'])
        if payload['expires_at'] is not None:
            payload['expires_at'] = datetime.fromisoformat(payload['expires_at'])
        lease = self._lease_cls(**payload)
        lease.validate()
        return lease


__all__ = ['CANON_PLATFORM_BILLING_SCHEDULER_LEASE_STORE', 'LEASE_SCHEMA_VERSION', 'PlatformSqliteBillingJobLeaseStore']
