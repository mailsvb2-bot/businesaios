from __future__ import annotations

"""Operational observability for runtime queue loops.

This registry records queue runtime facts only:
- worker tick counts
- scheduling health
- leadership / janitor activity
- derived alerts

It must not become policy or planning logic.
"""

from collections import deque
from dataclasses import dataclass, field, replace
from datetime import datetime
from threading import RLock
from typing import TYPE_CHECKING

from runtime.queue.job_contract import normalize_now
from runtime.queue.job_scheduler import ScheduleBatch
from runtime.queue.job_worker import WorkerTickReport

if TYPE_CHECKING:
    from runtime.queue.job_janitor import QueueJanitorReport
    from runtime.queue.queue_alerts import QueueAlert
    from runtime.queue.queue_leadership import QueueLeadershipReport


CANON_RUNTIME_QUEUE_OBSERVABILITY = True


def _require_queue_tenant_id(tenant_id: str | None, *, fallback_job_tenant_id: str | None = None) -> str:
    candidate = str(tenant_id or fallback_job_tenant_id or '').strip()
    if not candidate:
        raise ValueError('tenant_id is required')
    return candidate


@dataclass(frozen=True)
class WorkerLoopTelemetry:
    worker_id: str
    queue_name: str
    ticks: int = 0
    claimed: int = 0
    succeeded: int = 0
    failed: int = 0
    retried: int = 0
    dead_lettered: int = 0
    skipped: int = 0
    reclaimed_expired_claims: int = 0
    crashed: int = 0
    last_tick_at: datetime | None = None
    last_error: str | None = None
    stop_requested_at: datetime | None = None
    heartbeat_state: str = 'unknown'


@dataclass(frozen=True)
class QueueSchedulingTelemetry:
    queue_name: str
    queue_depth: int = 0
    active_claims: int = 0
    reclaimed_expired_claims: int = 0
    last_reason: str = 'unknown'
    last_seen_at: datetime | None = None


@dataclass(frozen=True)
class QueueLeadershipTelemetry:
    tenant_id: str
    queue_name: str
    role: str
    owner_id: str
    is_leader: bool = False
    fencing_token: int | None = None
    expires_at: datetime | None = None
    last_seen_at: datetime | None = None


@dataclass(frozen=True)
class QueueJanitorTelemetry:
    tenant_id: str
    queue_name: str
    runs: int = 0
    skipped_not_leader: int = 0
    reclaimed_expired_claims: int = 0
    pending_jobs: int = 0
    active_claims: int = 0
    retained_removed: int = 0
    last_reason: str = 'unknown'
    last_run_at: datetime | None = None


@dataclass(frozen=True)
class QueueAlertTelemetry:
    tenant_id: str
    queue_name: str
    code: str
    severity: str
    message: str
    count: int = 1
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None


@dataclass(frozen=True)
class QueueHistoryEvent:
    event_type: str
    tenant_id: str
    queue_name: str
    reason: str
    observed_at: datetime
    detail: str | None = None


@dataclass(frozen=True)
class QueueObservabilitySnapshot:
    workers: tuple[WorkerLoopTelemetry, ...] = field(default_factory=tuple)
    queues: tuple[QueueSchedulingTelemetry, ...] = field(default_factory=tuple)
    leadership: tuple[QueueLeadershipTelemetry, ...] = field(default_factory=tuple)
    janitors: tuple[QueueJanitorTelemetry, ...] = field(default_factory=tuple)
    alerts: tuple[QueueAlertTelemetry, ...] = field(default_factory=tuple)
    history: tuple[QueueHistoryEvent, ...] = field(default_factory=tuple)
    created_at: datetime = field(default_factory=normalize_now)


class QueueObservabilityRegistry:
    def __init__(self, *, history_limit: int = 500) -> None:
        self._lock = RLock()
        self._workers: dict[tuple[str, str], WorkerLoopTelemetry] = {}
        self._queues: dict[str, QueueSchedulingTelemetry] = {}
        self._leadership: dict[tuple[str, str, str], QueueLeadershipTelemetry] = {}
        self._janitors: dict[tuple[str, str], QueueJanitorTelemetry] = {}
        self._alerts: dict[tuple[str, str, str], QueueAlertTelemetry] = {}
        self._history: deque[QueueHistoryEvent] = deque(maxlen=max(1, int(history_limit)))

    def record_schedule_batch(self, batch: ScheduleBatch, *, tenant_id: str | None = None, now: datetime | None = None) -> None:
        moment = normalize_now(now)
        normalized_tenant_id = _require_queue_tenant_id(tenant_id, fallback_job_tenant_id=(batch.jobs[0].tenant_id if batch.jobs else None))
        with self._lock:
            current = self._queues.get(batch.queue_name)
            if current is None:
                current = QueueSchedulingTelemetry(queue_name=batch.queue_name)
            self._queues[batch.queue_name] = replace(
                current,
                queue_depth=int(batch.queue_depth),
                active_claims=int(batch.active_claims),
                reclaimed_expired_claims=int(batch.reclaimed_expired_claims),
                last_reason=str(batch.reason),
                last_seen_at=moment,
            )
            self._history.append(QueueHistoryEvent(event_type='schedule', tenant_id=normalized_tenant_id, queue_name=batch.queue_name, reason=str(batch.reason), observed_at=moment, detail=f'depth={int(batch.queue_depth)} active={int(batch.active_claims)}'))

    def record_worker_tick(self, report: WorkerTickReport, *, now: datetime | None = None) -> None:
        moment = normalize_now(now)
        key = (report.worker_id, report.queue_name)
        with self._lock:
            current = self._workers.get(key)
            if current is None:
                current = WorkerLoopTelemetry(worker_id=report.worker_id, queue_name=report.queue_name)
            self._workers[key] = replace(
                current,
                ticks=current.ticks + 1,
                claimed=current.claimed + int(report.claimed),
                succeeded=current.succeeded + int(report.succeeded),
                failed=current.failed + int(report.failed),
                retried=current.retried + int(report.retried),
                dead_lettered=current.dead_lettered + int(report.dead_lettered),
                skipped=current.skipped + int(report.skipped),
                reclaimed_expired_claims=current.reclaimed_expired_claims + int(report.reclaimed_expired_claims),
                last_tick_at=moment,
                heartbeat_state='running',
                last_error=None,
            )

    def record_worker_crash(self, *, worker_id: str, queue_name: str, error: str, now: datetime | None = None) -> None:
        moment = normalize_now(now)
        key = (str(worker_id).strip(), str(queue_name).strip())
        with self._lock:
            current = self._workers.get(key)
            if current is None:
                current = WorkerLoopTelemetry(worker_id=key[0], queue_name=key[1])
            self._workers[key] = replace(
                current,
                crashed=current.crashed + 1,
                last_tick_at=moment,
                heartbeat_state='crashed',
                last_error=str(error).strip() or 'worker_crash',
            )

    def record_stop_requested(self, *, worker_id: str, queue_name: str, now: datetime | None = None) -> None:
        moment = normalize_now(now)
        key = (str(worker_id).strip(), str(queue_name).strip())
        with self._lock:
            current = self._workers.get(key)
            if current is None:
                current = WorkerLoopTelemetry(worker_id=key[0], queue_name=key[1])
            self._workers[key] = replace(
                current,
                stop_requested_at=moment,
                heartbeat_state='stopping',
            )

    def record_leadership(self, report: QueueLeadershipReport, *, now: datetime | None = None) -> None:
        moment = normalize_now(now)
        key = (str(report.tenant_id).strip(), str(report.queue_name).strip(), str(report.role).strip())
        with self._lock:
            self._leadership[key] = QueueLeadershipTelemetry(
                tenant_id=key[0],
                queue_name=key[1],
                role=key[2],
                owner_id=str(report.owner_id).strip(),
                is_leader=bool(report.is_leader),
                fencing_token=report.fencing_token,
                expires_at=report.expires_at,
                last_seen_at=moment,
            )
            self._history.append(QueueHistoryEvent(event_type='leadership', tenant_id=key[0], queue_name=key[1], reason='leader' if report.is_leader else 'not_leader', observed_at=moment, detail=f'role={key[2]} owner={report.owner_id}'))

    def record_janitor_tick(self, report: QueueJanitorReport, *, now: datetime | None = None) -> None:
        moment = normalize_now(now)
        key = (str(report.tenant_id).strip(), str(report.queue_name).strip())
        with self._lock:
            current = self._janitors.get(key)
            if current is None:
                current = QueueJanitorTelemetry(tenant_id=key[0], queue_name=key[1])
            self._janitors[key] = replace(
                current,
                runs=current.runs + 1,
                skipped_not_leader=current.skipped_not_leader + (0 if report.is_leader else 1),
                reclaimed_expired_claims=current.reclaimed_expired_claims + int(report.reclaimed_expired_claims),
                pending_jobs=int(report.pending_jobs),
                active_claims=int(report.active_claims),
                last_reason=str(report.reason),
                last_run_at=moment,
            )
            self._history.append(QueueHistoryEvent(event_type='janitor', tenant_id=key[0], queue_name=key[1], reason=str(report.reason), observed_at=moment, detail=f'reclaimed={int(report.reclaimed_expired_claims)}'))

    def record_retention_prune(self, *, tenant_id: str, queue_name: str, removed: int, now: datetime | None = None) -> None:
        moment = normalize_now(now)
        key = (str(tenant_id).strip(), str(queue_name).strip())
        with self._lock:
            current = self._janitors.get(key)
            if current is None:
                current = QueueJanitorTelemetry(tenant_id=key[0], queue_name=key[1])
            self._janitors[key] = replace(
                current,
                retained_removed=current.retained_removed + max(0, int(removed)),
                last_run_at=moment,
            )
            self._history.append(QueueHistoryEvent(event_type='retention', tenant_id=key[0], queue_name=key[1], reason='retention_prune', observed_at=moment, detail=f'removed={max(0, int(removed))}'))

    def record_alerts(self, alerts: tuple[QueueAlert, ...], *, now: datetime | None = None) -> None:
        moment = normalize_now(now)
        with self._lock:
            for alert in alerts:
                key = (str(alert.tenant_id).strip(), str(alert.queue_name).strip(), str(alert.code).strip())
                current = self._alerts.get(key)
                if current is None:
                    self._alerts[key] = QueueAlertTelemetry(
                        tenant_id=key[0],
                        queue_name=key[1],
                        code=key[2],
                        severity=str(alert.severity).strip() or 'warning',
                        message=str(alert.message),
                        count=1,
                        first_seen_at=moment,
                        last_seen_at=moment,
                    )
                else:
                    self._alerts[key] = replace(
                        current,
                        severity=str(alert.severity).strip() or current.severity,
                        message=str(alert.message),
                        count=current.count + 1,
                        last_seen_at=moment,
                    )
                self._history.append(QueueHistoryEvent(event_type='alert', tenant_id=key[0], queue_name=key[1], reason=key[2], observed_at=moment, detail=str(alert.severity)))

    def snapshot(self) -> QueueObservabilitySnapshot:
        with self._lock:
            workers = tuple(sorted(self._workers.values(), key=lambda item: (item.queue_name, item.worker_id)))
            queues = tuple(sorted(self._queues.values(), key=lambda item: item.queue_name))
            leadership = tuple(sorted(self._leadership.values(), key=lambda item: (item.tenant_id, item.queue_name, item.role)))
            janitors = tuple(sorted(self._janitors.values(), key=lambda item: (item.tenant_id, item.queue_name)))
            alerts = tuple(sorted(self._alerts.values(), key=lambda item: (item.tenant_id, item.queue_name, item.severity, item.code)))
            history = tuple(self._history)
        return QueueObservabilitySnapshot(
            workers=workers,
            queues=queues,
            leadership=leadership,
            janitors=janitors,
            alerts=alerts,
            history=history,
        )


__all__ = [
    'CANON_RUNTIME_QUEUE_OBSERVABILITY',
    'QueueAlertTelemetry',
    'QueueHistoryEvent',
    'QueueJanitorTelemetry',
    'QueueLeadershipTelemetry',
    'QueueObservabilityRegistry',
    'QueueObservabilitySnapshot',
    'QueueSchedulingTelemetry',
    'WorkerLoopTelemetry',
]
