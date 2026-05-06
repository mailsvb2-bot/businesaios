from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CANON_REENCRYPTION_JOB_STORE = True


@dataclass(frozen=True)
class ReencryptionJob:
    job_id: str
    old_key_id: str
    new_key_id: str
    tenant_id: str | None = None
    connector_id: str | None = None
    status: str = 'pending'
    cursor_secret_ref: str | None = None
    processed_count: int = 0
    failed_count: int = 0
    metadata: dict[str, Any] | None = None


class SQLiteReencryptionJobStore:
    def __init__(self, db_path: str) -> None:
        self._db_path = str(db_path)
        self._ensure_schema()

    def put(self, job: ReencryptionJob) -> ReencryptionJob:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO security_reencryption_jobs(
                    job_id, old_key_id, new_key_id, tenant_id, connector_id, status, cursor_secret_ref,
                    processed_count, failed_count, metadata_json, updated_at_epoch_s
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    old_key_id=excluded.old_key_id,
                    new_key_id=excluded.new_key_id,
                    tenant_id=excluded.tenant_id,
                    connector_id=excluded.connector_id,
                    status=excluded.status,
                    cursor_secret_ref=excluded.cursor_secret_ref,
                    processed_count=excluded.processed_count,
                    failed_count=excluded.failed_count,
                    metadata_json=excluded.metadata_json,
                    updated_at_epoch_s=excluded.updated_at_epoch_s
                """,
                (
                    job.job_id,
                    job.old_key_id,
                    job.new_key_id,
                    job.tenant_id,
                    job.connector_id,
                    job.status,
                    job.cursor_secret_ref,
                    int(job.processed_count),
                    int(job.failed_count),
                    json.dumps(job.metadata or {}, ensure_ascii=False, sort_keys=True),
                    int(time.time()),
                ),
            )
            conn.commit()
        return job

    def get(self, job_id: str) -> ReencryptionJob:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT job_id, old_key_id, new_key_id, tenant_id, connector_id, status, cursor_secret_ref, processed_count, failed_count, metadata_json FROM security_reencryption_jobs WHERE job_id = ?",
                (str(job_id),),
            ).fetchone()
        if row is None:
            raise KeyError(f'unknown reencryption job: {job_id}')
        return ReencryptionJob(
            job_id=str(row[0]),
            old_key_id=str(row[1]),
            new_key_id=str(row[2]),
            tenant_id=row[3],
            connector_id=row[4],
            status=str(row[5]),
            cursor_secret_ref=row[6],
            processed_count=int(row[7]),
            failed_count=int(row[8]),
            metadata=dict(json.loads(str(row[9] or '{}'))),
        )

    def list_active(self) -> tuple[ReencryptionJob, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT job_id FROM security_reencryption_jobs WHERE status IN ('pending', 'running', 'paused') ORDER BY updated_at_epoch_s ASC, job_id ASC"
            ).fetchall()
        return tuple(self.get(str(row[0])) for row in rows)

    def list_active_for_tenant(self, *, tenant_id: str) -> tuple[ReencryptionJob, ...]:
        tenant_norm = str(tenant_id or '').strip()
        if not tenant_norm:
            raise ValueError('tenant_id is required')
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT job_id FROM security_reencryption_jobs WHERE tenant_id = ? AND status IN ('pending', 'running', 'paused') ORDER BY updated_at_epoch_s ASC, job_id ASC",
                (tenant_norm,),
            ).fetchall()
        return tuple(self.get(str(row[0])) for row in rows)

    def get_for_tenant(self, *, tenant_id: str, job_id: str) -> ReencryptionJob:
        tenant_norm = str(tenant_id or '').strip()
        if not tenant_norm:
            raise ValueError('tenant_id is required')
        job = self.get(job_id)
        if str(job.tenant_id or '').strip() != tenant_norm:
            raise PermissionError('cross-tenant reencryption job access denied')
        return job

    def _ensure_schema(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS security_reencryption_jobs (
                    job_id TEXT PRIMARY KEY,
                    old_key_id TEXT NOT NULL,
                    new_key_id TEXT NOT NULL,
                    tenant_id TEXT NULL,
                    connector_id TEXT NULL,
                    status TEXT NOT NULL,
                    cursor_secret_ref TEXT NULL,
                    processed_count INTEGER NOT NULL,
                    failed_count INTEGER NOT NULL,
                    metadata_json TEXT NOT NULL,
                    updated_at_epoch_s INTEGER NOT NULL
                )
                """
            )
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=NORMAL')
        return conn


__all__ = [
    'CANON_REENCRYPTION_JOB_STORE',
    'ReencryptionJob',
    'SQLiteReencryptionJobStore',
]
