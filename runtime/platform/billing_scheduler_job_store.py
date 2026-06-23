import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any
from collections.abc import Iterator


def require_tenant_id(value: object) -> str:
    tenant_id = str(value or "").strip()
    if not tenant_id:
        raise ValueError("tenant_id is required")
    return tenant_id


CANON_PLATFORM_BILLING_SCHEDULER_JOB_STORE = True
SCHEMA_VERSION = 1


class PlatformSqliteBillingJobRunStore:
    def __init__(self, *, sqlite_path: str, run_cls: type) -> None:
        self._path = str(sqlite_path).strip()
        self._run_cls = run_cls
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

    def save(self, run: Any) -> Any:
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

    def get(self, *, tenant_id: str, job_name: str, run_key: str) -> Any | None:
        tid = require_tenant_id(tenant_id)
        normalized_job = str(job_name).strip()
        normalized_key = str(run_key).strip()
        if not normalized_job or not normalized_key:
            raise ValueError('job_name and run_key are required')
        with self._connect() as conn:
            row = conn.execute('SELECT payload_json FROM billing_job_runs WHERE tenant_id = ? AND job_name = ? AND run_key = ?', (tid, normalized_job, normalized_key)).fetchone()
        return None if row is None else self._decode(row[0])

    def _decode(self, payload_json: str) -> Any:
        payload = json.loads(payload_json)
        payload['started_at'] = datetime.fromisoformat(payload['started_at'])
        if payload['finished_at'] is not None:
            payload['finished_at'] = datetime.fromisoformat(payload['finished_at'])
        run = self._run_cls(**payload)
        run.validate()
        return run


__all__ = ['CANON_PLATFORM_BILLING_SCHEDULER_JOB_STORE', 'PlatformSqliteBillingJobRunStore', 'SCHEMA_VERSION']
