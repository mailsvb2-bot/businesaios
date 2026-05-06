from __future__ import annotations

from datetime import datetime
from pathlib import Path
from threading import RLock

from runtime.queue._inmemory_job_store_ops import (
    claim_job,
    count_queue_jobs,
    get_active_claim,
    get_job,
    get_job_by_dedupe_key,
    list_due_jobs,
    mark_dead_letter,
    mark_failed,
    mark_succeeded,
    put_job,
    purge_terminal_job_records,
    reap_expired_claim_jobs,
    release_claim,
    renew_claim_lease,
    require_job,
    require_transitionable,
    reschedule_job,
    validate_claim_guard,
)
from runtime.queue._json_job_store_persistence import (
    flush_json_job_store_state,
    load_json_job_store_state,
    runtime_queue_store_path,
)
from runtime.queue.job_contract import JobRecord, JobState
from runtime.queue.job_store_backend import JobStoreBackend
from runtime.queue.job_store_sqlite import SqliteJobStore, runtime_queue_sqlite_store_path
from runtime.queue.queue_store_policy import DEFAULT_QUEUE_STORE_POLICY
from runtime.queue._persistent_job_store_support import build_default_job_store as build_default_queue_job_store
from runtime.queue import _persistent_job_store_methods as _persistent_job_store_methods


CANON_RUNTIME_QUEUE_JOB_STORE = True


class JobStore(JobStoreBackend):
    """Compatibility typing surface."""


class InMemoryJobStore(JobStoreBackend):
    def __init__(self) -> None:
        self._jobs: dict[tuple[str, str], JobRecord] = {}
        self._by_dedupe: dict[tuple[str, str], str] = {}
        self._claim_tokens: dict[tuple[str, str], int] = {}
        self._lock = RLock()

    @staticmethod
    def _validate_claim_guard(current: JobRecord, owner_id: str | None, fencing_token: int | None) -> None:
        validate_claim_guard(current, owner_id, fencing_token)

    def put(self, job: JobRecord) -> JobRecord:
        with self._lock:
            return put_job(jobs=self._jobs, by_dedupe=self._by_dedupe, claim_tokens=self._claim_tokens, job=job)

    def get(self, *, tenant_id: str, job_id: str) -> JobRecord | None:
        with self._lock:
            return get_job(jobs=self._jobs, tenant_id=tenant_id, job_id=job_id)

    def get_by_dedupe_key(self, *, tenant_id: str, dedupe_key: str) -> JobRecord | None:
        with self._lock:
            return get_job_by_dedupe_key(jobs=self._jobs, by_dedupe=self._by_dedupe, tenant_id=tenant_id, dedupe_key=dedupe_key)

    def count(self, *, tenant_id: str, queue_name: str, state: JobState | None = None) -> int:
        with self._lock:
            return count_queue_jobs(jobs=self._jobs, tenant_id=tenant_id, queue_name=queue_name, state=state)

    def list_due(self, *, tenant_id: str, queue_name: str, limit: int = DEFAULT_QUEUE_STORE_POLICY.default_due_limit, now: datetime | None = None) -> tuple[JobRecord, ...]:
        with self._lock:
            return list_due_jobs(jobs=self._jobs, tenant_id=tenant_id, queue_name=queue_name, limit=limit, now=now)

    def claim(self, *, tenant_id: str, job_id: str, owner_id: str, lease_seconds: int = DEFAULT_QUEUE_STORE_POLICY.default_claim_lease_seconds, now: datetime | None = None) -> JobRecord | None:
        with self._lock:
            return claim_job(
                jobs=self._jobs,
                claim_tokens=self._claim_tokens,
                tenant_id=tenant_id,
                job_id=job_id,
                owner_id=owner_id,
                lease_seconds=lease_seconds,
                now=now,
            )

    def get_active_claim(self, *, tenant_id: str, job_id: str, owner_id: str | None = None, fencing_token: int | None = None, now: datetime | None = None) -> JobRecord | None:
        with self._lock:
            return get_active_claim(
                jobs=self._jobs,
                tenant_id=tenant_id,
                job_id=job_id,
                owner_id=owner_id,
                fencing_token=fencing_token,
                now=now,
            )

    def renew_lease(self, *, tenant_id: str, job_id: str, owner_id: str, lease_seconds: int = DEFAULT_QUEUE_STORE_POLICY.default_claim_lease_seconds, fencing_token: int | None = None, now: datetime | None = None) -> JobRecord | None:
        with self._lock:
            return renew_claim_lease(
                jobs=self._jobs,
                tenant_id=tenant_id,
                job_id=job_id,
                owner_id=owner_id,
                lease_seconds=lease_seconds,
                fencing_token=fencing_token,
                now=now,
            )

    def release_claim(self, *, tenant_id: str, job_id: str, owner_id: str, fencing_token: int | None = None, now: datetime | None = None) -> JobRecord | None:
        with self._lock:
            return release_claim(
                jobs=self._jobs,
                tenant_id=tenant_id,
                job_id=job_id,
                owner_id=owner_id,
                fencing_token=fencing_token,
                now=now,
            )

    def reap_expired_claims(self, *, tenant_id: str, queue_name: str, now: datetime | None = None) -> int:
        with self._lock:
            return reap_expired_claim_jobs(jobs=self._jobs, tenant_id=tenant_id, queue_name=queue_name, now=now)

    def mark_succeeded(self, *, tenant_id: str, job_id: str, owner_id: str | None = None, fencing_token: int | None = None, now: datetime | None = None) -> JobRecord:
        with self._lock:
            return mark_succeeded(
                jobs=self._jobs,
                tenant_id=tenant_id,
                job_id=job_id,
                owner_id=owner_id,
                fencing_token=fencing_token,
                now=now,
            )

    def reschedule(self, *, tenant_id: str, job_id: str, delay_seconds: int, error: str, owner_id: str | None = None, fencing_token: int | None = None, now: datetime | None = None) -> JobRecord:
        with self._lock:
            return reschedule_job(
                jobs=self._jobs,
                tenant_id=tenant_id,
                job_id=job_id,
                delay_seconds=delay_seconds,
                error=error,
                owner_id=owner_id,
                fencing_token=fencing_token,
                now=now,
            )

    def mark_failed(self, *, tenant_id: str, job_id: str, error: str, owner_id: str | None = None, fencing_token: int | None = None, now: datetime | None = None) -> JobRecord:
        with self._lock:
            return mark_failed(
                jobs=self._jobs,
                tenant_id=tenant_id,
                job_id=job_id,
                error=error,
                owner_id=owner_id,
                fencing_token=fencing_token,
                now=now,
            )

    def mark_dead_letter(self, *, tenant_id: str, job_id: str, error: str, owner_id: str | None = None, fencing_token: int | None = None, now: datetime | None = None) -> JobRecord:
        with self._lock:
            return mark_dead_letter(
                jobs=self._jobs,
                tenant_id=tenant_id,
                job_id=job_id,
                error=error,
                owner_id=owner_id,
                fencing_token=fencing_token,
                now=now,
            )

    def purge_terminal_jobs(
        self,
        *,
        tenant_id: str,
        queue_name: str,
        states: tuple[JobState, ...],
        older_than: datetime,
        limit: int = DEFAULT_QUEUE_STORE_POLICY.default_purge_limit,
    ) -> int:
        with self._lock:
            return purge_terminal_job_records(
                jobs=self._jobs,
                by_dedupe=self._by_dedupe,
                claim_tokens=self._claim_tokens,
                tenant_id=tenant_id,
                queue_name=queue_name,
                states=states,
                older_than=older_than,
                limit=limit,
            )

    def close(self) -> None:
        return None

    def _transition(self, *, tenant_id: str, job_id: str, allowed_from: tuple[JobState, ...]) -> JobRecord:
        with self._lock:
            return require_transitionable(jobs=self._jobs, tenant_id=tenant_id, job_id=job_id, allowed_from=allowed_from)

    def _require(self, *, tenant_id: str, job_id: str) -> JobRecord:
        with self._lock:
            return require_job(jobs=self._jobs, tenant_id=tenant_id, job_id=job_id)


class PersistentJobStore(InMemoryJobStore):
    def __init__(self, path: str | Path | None = None) -> None:
        self._path = _persistent_job_store_methods.init_path(path)
        super().__init__()
        self._load()

    path = property(_persistent_job_store_methods.get_path)
    put = _persistent_job_store_methods.put
    claim = _persistent_job_store_methods.claim
    renew_lease = _persistent_job_store_methods.renew_lease
    release_claim = _persistent_job_store_methods.release_claim
    reap_expired_claims = _persistent_job_store_methods.reap_expired_claims
    mark_succeeded = _persistent_job_store_methods.mark_succeeded
    reschedule = _persistent_job_store_methods.reschedule
    mark_failed = _persistent_job_store_methods.mark_failed
    mark_dead_letter = _persistent_job_store_methods.mark_dead_letter
    purge_terminal_jobs = _persistent_job_store_methods.purge_terminal_jobs
    _load = _persistent_job_store_methods._load
    _flush = _persistent_job_store_methods._flush


class SqlitePersistentJobStore(SqliteJobStore):
    pass


def build_default_job_store() -> JobStoreBackend:
    return build_default_queue_job_store(
        memory_factory=InMemoryJobStore,
        sqlite_factory=SqlitePersistentJobStore,
        persistent_factory=PersistentJobStore,
    )


__all__ = [
    "CANON_RUNTIME_QUEUE_JOB_STORE",
    "InMemoryJobStore",
    "JobStore",
    "PersistentJobStore",
    "SqlitePersistentJobStore",
    "build_default_job_store",
    "runtime_queue_sqlite_store_path",
    "runtime_queue_store_path",
]
