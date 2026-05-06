from __future__ import annotations

"""Scheduler for due queue jobs.

This scheduler never invents work.
It only selects already-persisted due jobs for workers.
"""

from dataclasses import dataclass, field
from datetime import datetime

from core.tenancy.normalization import require_tenant_id
from runtime.queue.capability_throttle_policy import (
    CapabilityThrottlePolicy,
    CapabilityThrottleVerdict,
    resolve_capability_key,
)
from runtime.queue.job_contract import JobRecord, JobState, normalize_now
from runtime.queue.job_lease_manager import JobLeaseManager
from runtime.queue.job_store import JobStore
from runtime.queue.tenant_fair_scheduler import (
    TenantFairScheduleReport,
    TenantFairScheduler,
    TenantQueuePressure,
)
from runtime.queue.throttle_policy import ThrottlePolicy


CANON_RUNTIME_QUEUE_SCHEDULER = True


@dataclass(frozen=True)
class ScheduleBatch:
    queue_name: str
    jobs: tuple[JobRecord, ...]
    reason: str
    reclaimed_expired_claims: int = 0
    queue_depth: int = 0
    active_claims: int = 0
    fair_schedule: TenantFairScheduleReport | None = None
    capability_previews: dict[str, CapabilityThrottleVerdict] = field(default_factory=dict)


class JobScheduler:
    def __init__(
        self,
        *,
        store: JobStore,
        throttle_policy: ThrottlePolicy | None = None,
        lease_manager: JobLeaseManager | None = None,
        fair_scheduler: TenantFairScheduler | None = None,
        capability_throttle_policy: CapabilityThrottlePolicy | None = None,
    ) -> None:
        self._store = store
        self._throttle_policy = throttle_policy or ThrottlePolicy()
        self._lease_manager = lease_manager or JobLeaseManager(store=store)
        self._fair_scheduler = fair_scheduler or TenantFairScheduler()
        self._capability_throttle_policy = capability_throttle_policy or CapabilityThrottlePolicy()

    def select_due_jobs(self, *, tenant_id: str, queue_name: str, now: datetime | None = None) -> ScheduleBatch:
        moment = normalize_now(now)
        normalized_tenant_id = require_tenant_id(tenant_id)
        queue = str(queue_name or '').strip()
        if not queue:
            raise ValueError('queue_name is required')
        reclaimed = self._lease_manager.reap_expired_claims(tenant_id=normalized_tenant_id, queue_name=queue, now=moment)
        queue_depth = self._store.count(tenant_id=normalized_tenant_id, queue_name=queue, state=JobState.PENDING)
        active_claims = self._store.count(tenant_id=normalized_tenant_id, queue_name=queue, state=JobState.CLAIMED)
        throttle = self._throttle_policy.evaluate(queue_depth=queue_depth, active_claims=active_claims)
        fair_schedule = self._fair_scheduler.plan_allocations(
            queue_name=queue,
            pressures=(TenantQueuePressure(tenant_id=normalized_tenant_id, queue_name=queue, pending_jobs=queue_depth, active_claims=active_claims),),
            total_claim_limit=throttle.max_claim_count,
            now=moment,
        )
        tenant_limit = throttle.max_claim_count
        if fair_schedule.allocations:
            tenant_limit = min(tenant_limit, max(0, int(fair_schedule.allocations[0].claim_limit)))
        due = self._store.list_due(tenant_id=normalized_tenant_id, queue_name=queue, limit=max(0, int(tenant_limit)), now=moment)
        jobs: list[JobRecord] = []
        previews: dict[str, CapabilityThrottleVerdict] = {}
        provisional_counts: dict[str, int] = {}
        for candidate in due:
            try:
                capability = resolve_capability_key(job_type=candidate.job_type, payload=candidate.payload, tags=candidate.tags)
            except ValueError:
                continue
            preview = self._capability_throttle_policy.preview(
                tenant_id=normalized_tenant_id,
                queue_name=queue,
                capability=capability,
                requested_claims=provisional_counts.get(capability, 0) + 1,
                active_claims=active_claims + len(jobs),
                now=moment,
            )
            if preview.allowed_claims <= provisional_counts.get(capability, 0):
                continue
            provisional_counts[capability] = provisional_counts.get(capability, 0) + 1
            jobs.append(candidate)
            previews[candidate.job_id] = preview
        return ScheduleBatch(
            queue_name=queue,
            jobs=tuple(jobs),
            reason=throttle.reason,
            reclaimed_expired_claims=reclaimed,
            queue_depth=queue_depth,
            active_claims=active_claims,
            fair_schedule=fair_schedule,
            capability_previews=previews,
        )

    def commit_claimed_job(self, *, job: JobRecord, now: datetime | None = None) -> None:
        moment = normalize_now(now)
        capability = resolve_capability_key(job_type=job.job_type, payload=job.payload, tags=job.tags)
        self._capability_throttle_policy.commit(
            tenant_id=job.tenant_id,
            queue_name=job.queue_name,
            capability=capability,
            consumed_claims=1,
            now=moment,
        )


__all__ = [
    "CANON_RUNTIME_QUEUE_SCHEDULER",
    "JobScheduler",
    "ScheduleBatch",
]
