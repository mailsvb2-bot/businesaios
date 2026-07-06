"""Queue janitor for recovery-safe operational maintenance.

Responsibilities:
- reclaim expired claims
- report queue depth / active claims after maintenance
- optionally gate janitor work behind a single leader lease

Non-responsibilities:
- create new jobs
- decide business actions
- bypass canonical execution flow
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from runtime.queue.job_contract import JobState, normalize_now
from runtime.queue.job_store import JobStore
from runtime.queue.queue_leadership import QueueLeadershipCoordinator
from runtime.queue.queue_operational_contracts import QueueJanitorReport, QueueLeadershipReport

CANON_RUNTIME_QUEUE_JANITOR = True

class JobQueueJanitor:
    def __init__(
        self,
        *,
        store: JobStore,
        leadership: QueueLeadershipCoordinator | None = None,
        observability: Any | None = None,
        history_store: Any | None = None,
    ) -> None:
        self._store = store
        self._leadership = leadership
        self._observability = observability
        self._history_store = history_store

    def tick(self, *, tenant_id: str, queue_name: str, now: datetime | None = None) -> QueueJanitorReport:
        moment = normalize_now(now)
        qn = str(queue_name).strip()
        if not qn:
            raise ValueError("queue_name is required")
        leadership_report: QueueLeadershipReport | None = None
        if self._leadership is not None:
            leadership_report = self._leadership.campaign_or_heartbeat(tenant_id=tenant_id, now=moment)
            if self._observability is not None:
                self._observability.record_leadership(leadership_report, now=moment)
            if not leadership_report.is_leader:
                report = QueueJanitorReport(
                    tenant_id=str(tenant_id).strip(),
                    queue_name=qn,
                    is_leader=False,
                    leadership_fencing_token=leadership_report.fencing_token,
                    reason="leadership_not_acquired",
                    ran_at=moment,
                )
                self._record(report=report, now=moment)
                return report

        reclaimed = self._store.reap_expired_claims(tenant_id=tenant_id, queue_name=qn, now=moment)
        pending_jobs = self._store.count(tenant_id=tenant_id, queue_name=qn, state=JobState.PENDING)
        active_claims = self._store.count(tenant_id=tenant_id, queue_name=qn, state=JobState.CLAIMED)
        report = QueueJanitorReport(
            tenant_id=str(tenant_id).strip(),
            queue_name=qn,
            reclaimed_expired_claims=reclaimed,
            pending_jobs=pending_jobs,
            active_claims=active_claims,
            is_leader=True,
            leadership_fencing_token=(leadership_report.fencing_token if leadership_report is not None else None),
            reason="janitor_tick",
            ran_at=moment,
        )
        self._record(report=report, now=moment)
        return report

    def _record(self, *, report: QueueJanitorReport, now: datetime) -> None:
        if self._observability is not None:
            self._observability.record_janitor_tick(report, now=now)
        if self._history_store is not None:
            self._history_store.record_janitor_tick(report)


__all__ = [
    "CANON_RUNTIME_QUEUE_JANITOR",
    "JobQueueJanitor",
    "QueueJanitorReport",
]
