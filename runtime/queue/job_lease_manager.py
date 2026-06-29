"""Lease lifecycle manager for runtime queue jobs.

Responsibilities:
- claim jobs safely
- renew / heartbeat active claims
- release claims
- reclaim expired claims

This module is operational-only and must not become a second brain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from runtime.queue.job_contract import JobLease, JobRecord, normalize_now, utc_now
from runtime.queue.job_store_backend import JobStoreBackend
from runtime.queue.job_visibility_timeout import JobVisibilityTimeout, JobVisibilityWindow

CANON_RUNTIME_QUEUE_JOB_LEASE_MANAGER = True

@dataclass(frozen=True)
class LeaseHeartbeatReport:
    job: JobRecord
    heartbeat_at: datetime = field(default_factory=utc_now)
    visibility_window: JobVisibilityWindow | None = None


class JobLeaseManager:
    def __init__(
        self,
        *,
        store: JobStoreBackend,
        visibility_timeout: JobVisibilityTimeout | None = None,
        default_owner_id: str = "runtime-queue-worker",
    ) -> None:
        owner = str(default_owner_id).strip()
        if not owner:
            raise ValueError("default_owner_id is required")
        self._store = store
        self._visibility_timeout = visibility_timeout or JobVisibilityTimeout()
        self._default_owner_id = owner

    @property
    def default_owner_id(self) -> str:
        return self._default_owner_id

    def claim(
        self,
        *,
        tenant_id: str,
        job_id: str,
        owner_id: str | None = None,
        lease_seconds: int | None = None,
        now: datetime | None = None,
    ) -> JobRecord | None:
        current = self._store.get(tenant_id=tenant_id, job_id=job_id)
        if current is None:
            return None
        effective_owner = self._resolve_owner(owner_id)
        effective_lease_seconds = (
            max(1, int(lease_seconds))
            if lease_seconds is not None
            else self._visibility_timeout.lease_seconds_for(current)
        )
        return self._store.claim(
            tenant_id=tenant_id,
            job_id=job_id,
            owner_id=effective_owner,
            lease_seconds=effective_lease_seconds,
            now=normalize_now(now),
        )

    def claim_due_job(
        self,
        *,
        tenant_id: str,
        queue_name: str,
        owner_id: str | None = None,
        now: datetime | None = None,
    ) -> JobRecord | None:
        moment = normalize_now(now)
        due_jobs = self._store.list_due(
            tenant_id=tenant_id,
            queue_name=queue_name,
            limit=1,
            now=moment,
        )
        if not due_jobs:
            return None
        return self.claim(
            tenant_id=tenant_id,
            job_id=due_jobs[0].job_id,
            owner_id=owner_id,
            now=moment,
        )

    def heartbeat(
        self,
        *,
        tenant_id: str,
        job_id: str,
        owner_id: str | None = None,
        lease_seconds: int | None = None,
        now: datetime | None = None,
    ) -> LeaseHeartbeatReport | None:
        current = self._store.get(tenant_id=tenant_id, job_id=job_id)
        if current is None:
            return None
        effective_owner = self._resolve_owner(owner_id)
        effective_lease_seconds = (
            max(1, int(lease_seconds))
            if lease_seconds is not None
            else self._visibility_timeout.lease_seconds_for(current)
        )
        moment = normalize_now(now)
        renewed = self._store.renew_lease(
            tenant_id=tenant_id,
            job_id=job_id,
            owner_id=effective_owner,
            lease_seconds=effective_lease_seconds,
            fencing_token=(current.lease.fencing_token if current.lease is not None else None),
            now=moment,
        )
        if renewed is None:
            return None
        return LeaseHeartbeatReport(
            job=renewed,
            heartbeat_at=moment,
            visibility_window=self._visibility_timeout.window_for(renewed),
        )

    def release(
        self,
        *,
        tenant_id: str,
        job_id: str,
        owner_id: str | None = None,
        now: datetime | None = None,
    ) -> JobRecord | None:
        current = self._store.get(tenant_id=tenant_id, job_id=job_id)
        return self._store.release_claim(
            tenant_id=tenant_id,
            job_id=job_id,
            owner_id=self._resolve_owner(owner_id),
            fencing_token=(current.lease.fencing_token if current is not None and current.lease is not None else None),
            now=normalize_now(now),
        )

    def reap_expired_claims(
        self,
        *,
        tenant_id: str,
        queue_name: str,
        now: datetime | None = None,
    ) -> int:
        return self._store.reap_expired_claims(
            tenant_id=tenant_id,
            queue_name=queue_name,
            now=normalize_now(now),
        )

    @staticmethod
    def remaining_lease_seconds(*, lease: JobLease, now: datetime | None = None) -> int:
        return max(0, int((lease.expires_at - normalize_now(now)).total_seconds()))

    def visibility_window_for(self, *, job: JobRecord) -> JobVisibilityWindow:
        return self._visibility_timeout.window_for(job)

    def _resolve_owner(self, owner_id: str | None) -> str:
        value = str(owner_id or self._default_owner_id).strip()
        if not value:
            raise ValueError("owner_id is required")
        return value


__all__ = [
    "CANON_RUNTIME_QUEUE_JOB_LEASE_MANAGER",
    "JobLeaseManager",
    "LeaseHeartbeatReport",
]
