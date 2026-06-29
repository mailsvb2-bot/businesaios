"""Operational SLO evaluation for runtime queue health.

This module reads queue facts and emits health verdicts. It does not change
queue state and must never become planning logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from core.tenancy.normalization import require_tenant_id
from runtime.queue.job_contract import JobState, normalize_now
from runtime.queue.job_store_backend import JobStoreBackend
from runtime.queue.queue_operational_contracts import QueueSLOReport

CANON_RUNTIME_QUEUE_SLO = True


@dataclass(frozen=True)
class QueueSLOThresholds:
    max_pending_jobs: int = 100
    max_active_claims: int = 50
    max_dead_letter_jobs: int = 25
    max_stale_janitor_age_seconds: int = 120
    max_stale_leader_age_seconds: int = 120




class QueueSLOEvaluator:
    def __init__(
        self,
        *,
        store: JobStoreBackend,
        observability: Any,
        thresholds: QueueSLOThresholds | None = None,
    ) -> None:
        self._store = store
        self._observability = observability
        self._thresholds = thresholds or QueueSLOThresholds()

    def evaluate(self, *, tenant_id: str, queue_name: str, now: datetime | None = None):
        moment = normalize_now(now)
        normalized_tenant_id = require_tenant_id(tenant_id)
        normalized_queue_name = str(queue_name or '').strip()
        if not normalized_queue_name:
            raise ValueError('queue_name is required')
        pending_jobs = self._store.count(tenant_id=normalized_tenant_id, queue_name=normalized_queue_name, state=JobState.PENDING)
        active_claims = self._store.count(tenant_id=normalized_tenant_id, queue_name=normalized_queue_name, state=JobState.CLAIMED)
        dead_letter_jobs = self._store.count(tenant_id=normalized_tenant_id, queue_name=normalized_queue_name, state=JobState.DEAD_LETTER)

        snapshot = self._observability.snapshot()
        janitor_age = None
        for item in snapshot.janitors:
            if item.tenant_id == normalized_tenant_id and item.queue_name == normalized_queue_name and item.last_run_at is not None:
                janitor_age = max(0, int((moment - item.last_run_at).total_seconds()))
                break
        leader_age = None
        leadership_seen = [
            item for item in snapshot.leadership
            if item.tenant_id == normalized_tenant_id and item.queue_name == normalized_queue_name and item.last_seen_at is not None
        ]
        if leadership_seen:
            leader_age = max(0, int((moment - max(item.last_seen_at for item in leadership_seen if item.last_seen_at is not None)).total_seconds()))

        reasons: list[str] = []
        if pending_jobs > self._thresholds.max_pending_jobs:
            reasons.append("pending_jobs_exceeded")
        if active_claims > self._thresholds.max_active_claims:
            reasons.append("active_claims_exceeded")
        if dead_letter_jobs > self._thresholds.max_dead_letter_jobs:
            reasons.append("dead_letter_jobs_exceeded")
        if janitor_age is None or janitor_age > self._thresholds.max_stale_janitor_age_seconds:
            reasons.append("janitor_stale")
        if leader_age is None or leader_age > self._thresholds.max_stale_leader_age_seconds:
            reasons.append("leadership_stale")
        status = 'healthy'
        if reasons:
            critical_reasons = {'dead_letter_jobs_exceeded', 'janitor_stale', 'leadership_stale'}
            status = 'critical' if any(reason in critical_reasons for reason in reasons) else 'degraded'
        return QueueSLOReport(
            tenant_id=normalized_tenant_id,
            queue_name=normalized_queue_name,
            ok=not reasons,
            status=status,
            reasons=tuple(reasons),
            pending_jobs=pending_jobs,
            active_claims=active_claims,
            dead_letter_jobs=dead_letter_jobs,
            janitor_stale_seconds=janitor_age,
            leader_stale_seconds=leader_age,
        )


__all__ = [
    "CANON_RUNTIME_QUEUE_SLO",
    "QueueSLOEvaluator",
    "QueueSLOReport",
    "QueueSLOThresholds",
]
