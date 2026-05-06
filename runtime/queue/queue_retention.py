from __future__ import annotations

"""Retention cleanup for runtime queue terminal jobs.

This layer is operational hygiene only:
- prune old terminal jobs
- keep queue persistence bounded
- never invent business logic or decisions
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from runtime.queue.job_contract import JobState, normalize_now
from runtime.queue.job_store_backend import JobStoreBackend


CANON_RUNTIME_QUEUE_RETENTION = True


@dataclass(frozen=True)
class QueueRetentionPolicy:
    succeeded_ttl_seconds: int = 86400
    failed_ttl_seconds: int = 7 * 86400
    dead_letter_ttl_seconds: int = 30 * 86400
    cancelled_ttl_seconds: int = 7 * 86400
    batch_limit: int = 1000

    def cutoff_for(self, state: JobState, *, now: datetime | None = None) -> datetime:
        moment = normalize_now(now)
        ttl = self.ttl_seconds_for(state)
        return moment - timedelta(seconds=ttl)

    def ttl_seconds_for(self, state: JobState) -> int:
        if state is JobState.SUCCEEDED:
            return max(1, int(self.succeeded_ttl_seconds))
        if state is JobState.FAILED:
            return max(1, int(self.failed_ttl_seconds))
        if state is JobState.DEAD_LETTER:
            return max(1, int(self.dead_letter_ttl_seconds))
        if state is JobState.CANCELLED:
            return max(1, int(self.cancelled_ttl_seconds))
        raise ValueError(f"unsupported retention state: {state.value}")


@dataclass(frozen=True)
class QueueRetentionReport:
    tenant_id: str
    queue_name: str
    removed_succeeded: int = 0
    removed_failed: int = 0
    removed_dead_letter: int = 0
    removed_cancelled: int = 0
    ran_at: datetime | None = None

    @property
    def total_removed(self) -> int:
        return int(self.removed_succeeded + self.removed_failed + self.removed_dead_letter + self.removed_cancelled)


class QueueRetentionManager:
    def __init__(self, *, store: JobStoreBackend, policy: QueueRetentionPolicy | None = None) -> None:
        self._store = store
        self._policy = policy or QueueRetentionPolicy()

    @property
    def policy(self) -> QueueRetentionPolicy:
        return self._policy

    def prune(self, *, tenant_id: str, queue_name: str, now: datetime | None = None) -> QueueRetentionReport:
        moment = normalize_now(now)
        removed_succeeded = self._store.purge_terminal_jobs(
            tenant_id=tenant_id,
            queue_name=queue_name,
            states=(JobState.SUCCEEDED,),
            older_than=self._policy.cutoff_for(JobState.SUCCEEDED, now=moment),
            limit=self._policy.batch_limit,
        )
        removed_failed = self._store.purge_terminal_jobs(
            tenant_id=tenant_id,
            queue_name=queue_name,
            states=(JobState.FAILED,),
            older_than=self._policy.cutoff_for(JobState.FAILED, now=moment),
            limit=self._policy.batch_limit,
        )
        removed_dead_letter = self._store.purge_terminal_jobs(
            tenant_id=tenant_id,
            queue_name=queue_name,
            states=(JobState.DEAD_LETTER,),
            older_than=self._policy.cutoff_for(JobState.DEAD_LETTER, now=moment),
            limit=self._policy.batch_limit,
        )
        removed_cancelled = self._store.purge_terminal_jobs(
            tenant_id=tenant_id,
            queue_name=queue_name,
            states=(JobState.CANCELLED,),
            older_than=self._policy.cutoff_for(JobState.CANCELLED, now=moment),
            limit=self._policy.batch_limit,
        )
        return QueueRetentionReport(
            tenant_id=str(tenant_id).strip(),
            queue_name=str(queue_name).strip(),
            removed_succeeded=removed_succeeded,
            removed_failed=removed_failed,
            removed_dead_letter=removed_dead_letter,
            removed_cancelled=removed_cancelled,
            ran_at=moment,
        )


__all__ = [
    "CANON_RUNTIME_QUEUE_RETENTION",
    "QueueRetentionManager",
    "QueueRetentionPolicy",
    "QueueRetentionReport",
]
