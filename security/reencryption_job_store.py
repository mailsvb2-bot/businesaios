from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from runtime.platform.security_sqlite_stores import SQLiteReencryptionJobStoreBackend

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
    """Security-facing reencryption job store facade.

    SQLite ownership lives in runtime.platform.security_sqlite_stores.
    """

    def __init__(self, db_path: str) -> None:
        self._backend = SQLiteReencryptionJobStoreBackend(db_path, ReencryptionJob)

    def put(self, job: ReencryptionJob) -> ReencryptionJob:
        return self._backend.put(job)

    def get(self, job_id: str) -> ReencryptionJob:
        return self._backend.get(job_id)

    def list_active(self) -> tuple[ReencryptionJob, ...]:
        return self._backend.list_active()

    def list_active_for_tenant(self, *, tenant_id: str) -> tuple[ReencryptionJob, ...]:
        tenant_norm = str(tenant_id or '').strip()
        if not tenant_norm:
            raise ValueError('tenant_id is required')
        return self._backend.list_active_for_tenant(tenant_id=tenant_norm)

    def get_for_tenant(self, *, tenant_id: str, job_id: str) -> ReencryptionJob:
        tenant_norm = str(tenant_id or '').strip()
        if not tenant_norm:
            raise ValueError('tenant_id is required')
        job = self.get(job_id)
        if str(job.tenant_id or '').strip() != tenant_norm:
            raise PermissionError('cross-tenant reencryption job access denied')
        return job


__all__ = ['CANON_REENCRYPTION_JOB_STORE', 'ReencryptionJob', 'SQLiteReencryptionJobStore']
