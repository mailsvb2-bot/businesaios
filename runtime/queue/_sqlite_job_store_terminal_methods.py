from __future__ import annotations

from runtime.queue.job_contract import JobState
from runtime.queue._sqlite_job_store_db import transition_terminal
from runtime.queue._sqlite_job_store_runtime import purge_terminal_jobs_sqlite
from runtime.queue.queue_store_policy import DEFAULT_QUEUE_STORE_POLICY


def mark_succeeded(self, *, tenant_id: str, job_id: str, owner_id: str | None = None, fencing_token: int | None = None, now=None):
    self._ensure_open()
    with self._lock, self._tx() as db:
        return transition_terminal(
            db,
            tenant_id=self._require_tenant_id(tenant_id),
            job_id=self._require_job_id(job_id),
            allowed_from=(JobState.CLAIMED,),
            next_state=JobState.SUCCEEDED,
            error=None,
            owner_id=owner_id,
            fencing_token=fencing_token,
            now=now,
        )


def mark_failed(self, *, tenant_id: str, job_id: str, error: str, owner_id: str | None = None, fencing_token: int | None = None, now=None):
    self._ensure_open()
    with self._lock, self._tx() as db:
        return transition_terminal(
            db,
            tenant_id=self._require_tenant_id(tenant_id),
            job_id=self._require_job_id(job_id),
            allowed_from=(JobState.CLAIMED,),
            next_state=JobState.FAILED,
            error=str(error),
            owner_id=owner_id,
            fencing_token=fencing_token,
            now=now,
        )


def mark_dead_letter(self, *, tenant_id: str, job_id: str, error: str, owner_id: str | None = None, fencing_token: int | None = None, now=None):
    self._ensure_open()
    with self._lock, self._tx() as db:
        return transition_terminal(
            db,
            tenant_id=self._require_tenant_id(tenant_id),
            job_id=self._require_job_id(job_id),
            allowed_from=(JobState.PENDING, JobState.CLAIMED, JobState.FAILED),
            next_state=JobState.DEAD_LETTER,
            error=str(error),
            owner_id=owner_id,
            fencing_token=fencing_token,
            now=now,
        )


def purge_terminal_jobs(self, *, tenant_id: str, queue_name: str, states: tuple[JobState, ...], older_than, limit: int = DEFAULT_QUEUE_STORE_POLICY.default_purge_limit) -> int:
    self._ensure_open()
    tid = self._require_tenant_id(tenant_id)
    qn = self._require_queue_name(queue_name)
    with self._lock, self._tx() as db:
        return purge_terminal_jobs_sqlite(
            db=db,
            tenant_id=tid,
            queue_name=qn,
            states=states,
            older_than=older_than,
            limit=limit,
        )


def reschedule(self, *, tenant_id: str, job_id: str, delay_seconds: int, error: str, owner_id: str | None = None, fencing_token: int | None = None, now=None):
    self._ensure_open()
    with self._lock, self._tx() as db:
        return self._reschedule_claimed_job_sqlite(
            db=db,
            require_transitionable=self._require_transitionable,
            fetch_job=self._fetch_job,
            tenant_id=self._require_tenant_id(tenant_id),
            job_id=self._require_job_id(job_id),
            delay_seconds=delay_seconds,
            error=str(error),
            owner_id=owner_id,
            fencing_token=fencing_token,
            now=now,
        )
