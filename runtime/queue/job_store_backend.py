from __future__ import annotations

"""Canonical backend contract for runtime queue persistence.

Infrastructure only:
- persist already-decided jobs
- provide atomic operational transitions for workers
- never introduce a second decision path
"""

from datetime import datetime
from typing import Protocol, runtime_checkable

from runtime.queue.job_contract import JobRecord, JobState


CANON_RUNTIME_QUEUE_JOB_STORE_BACKEND = True


@runtime_checkable
class JobStoreBackend(Protocol):
    def put(self, job: JobRecord) -> JobRecord: ...
    def get(self, *, tenant_id: str, job_id: str) -> JobRecord | None: ...
    def get_by_dedupe_key(self, *, tenant_id: str, dedupe_key: str) -> JobRecord | None: ...

    def count(
        self,
        *,
        tenant_id: str,
        queue_name: str,
        state: JobState | None = None,
    ) -> int: ...

    def list_due(
        self,
        *,
        tenant_id: str,
        queue_name: str,
        limit: int = 100,
        now: datetime | None = None,
    ) -> tuple[JobRecord, ...]: ...

    def claim(
        self,
        *,
        tenant_id: str,
        job_id: str,
        owner_id: str,
        lease_seconds: int = 60,
        now: datetime | None = None,
    ) -> JobRecord | None: ...

    def get_active_claim(
        self,
        *,
        tenant_id: str,
        job_id: str,
        owner_id: str | None = None,
        fencing_token: int | None = None,
        now: datetime | None = None,
    ) -> JobRecord | None: ...

    def renew_lease(
        self,
        *,
        tenant_id: str,
        job_id: str,
        owner_id: str,
        lease_seconds: int = 60,
        fencing_token: int | None = None,
        now: datetime | None = None,
    ) -> JobRecord | None: ...

    def release_claim(
        self,
        *,
        tenant_id: str,
        job_id: str,
        owner_id: str,
        fencing_token: int | None = None,
        now: datetime | None = None,
    ) -> JobRecord | None: ...

    def reap_expired_claims(
        self,
        *,
        tenant_id: str,
        queue_name: str,
        now: datetime | None = None,
    ) -> int: ...

    def mark_succeeded(
        self,
        *,
        tenant_id: str,
        job_id: str,
        owner_id: str | None = None,
        fencing_token: int | None = None,
        now: datetime | None = None,
    ) -> JobRecord: ...

    def reschedule(
        self,
        *,
        tenant_id: str,
        job_id: str,
        delay_seconds: int,
        error: str,
        owner_id: str | None = None,
        fencing_token: int | None = None,
        now: datetime | None = None,
    ) -> JobRecord: ...

    def mark_failed(
        self,
        *,
        tenant_id: str,
        job_id: str,
        error: str,
        owner_id: str | None = None,
        fencing_token: int | None = None,
        now: datetime | None = None,
    ) -> JobRecord: ...

    def mark_dead_letter(
        self,
        *,
        tenant_id: str,
        job_id: str,
        error: str,
        owner_id: str | None = None,
        fencing_token: int | None = None,
        now: datetime | None = None,
    ) -> JobRecord: ...

    def close(self) -> None: ...


__all__ = [
    "CANON_RUNTIME_QUEUE_JOB_STORE_BACKEND",
    "JobStoreBackend",
]
