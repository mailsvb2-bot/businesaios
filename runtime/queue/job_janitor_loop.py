from __future__ import annotations

"""Polling loop for queue janitor maintenance.

Operational only:
- reclaim expired claims
- run retention pruning
- optionally gated by operational leadership
"""

from dataclasses import dataclass
from datetime import datetime

from runtime.queue.job_contract import normalize_now
from runtime.queue.job_janitor import JobQueueJanitor, QueueJanitorReport
from runtime.queue.job_stop_token import JobStopToken
from runtime.queue.queue_retention import QueueRetentionManager, QueueRetentionReport


CANON_RUNTIME_QUEUE_JANITOR_LOOP = True


@dataclass(frozen=True)
class JanitorLoopTick:
    janitor: QueueJanitorReport
    retention: QueueRetentionReport | None = None


@dataclass(frozen=True)
class JanitorLoopReport:
    tenant_id: str
    queue_name: str
    ticks: int = 0
    crashes: int = 0
    reclaimed_expired_claims: int = 0
    retained_removed: int = 0
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    last_error: str | None = None


class JobJanitorLoop:
    def __init__(
        self,
        *,
        janitor: JobQueueJanitor,
        tenant_id: str,
        queue_name: str,
        retention: QueueRetentionManager | None = None,
        stop_token: JobStopToken | None = None,
        idle_sleep_seconds: float = 1.0,
        max_consecutive_crashes: int = 3,
    ) -> None:
        self._janitor = janitor
        self._tenant_id = str(tenant_id).strip()
        self._queue_name = str(queue_name).strip()
        if not self._tenant_id:
            raise ValueError("tenant_id is required")
        if not self._queue_name:
            raise ValueError("queue_name is required")
        self._retention = retention
        self._stop_token = stop_token or JobStopToken()
        self._idle_sleep_seconds = max(0.01, float(idle_sleep_seconds))
        self._max_consecutive_crashes = max(1, int(max_consecutive_crashes))

    @property
    def stop_token(self) -> JobStopToken:
        return self._stop_token

    def run(self, *, max_ticks: int | None = None, now: datetime | None = None) -> JanitorLoopReport:
        started_at = normalize_now(now)
        ticks = 0
        crashes = 0
        consecutive_crashes = 0
        reclaimed_expired_claims = 0
        retained_removed = 0
        last_error: str | None = None
        while not self._stop_token.is_stop_requested():
            if max_ticks is not None and ticks >= int(max_ticks):
                break
            try:
                moment = normalize_now()
                janitor_report = self._janitor.tick(tenant_id=self._tenant_id, queue_name=self._queue_name, now=moment)
                reclaimed_expired_claims += int(janitor_report.reclaimed_expired_claims)
                if janitor_report.is_leader and self._retention is not None:
                    retention_report = self._retention.prune(tenant_id=self._tenant_id, queue_name=self._queue_name, now=moment)
                    retained_removed += retention_report.total_removed
                    observability = getattr(self._janitor, '_observability', None)
                    if observability is not None:
                        observability.record_retention_prune(tenant_id=self._tenant_id, queue_name=self._queue_name, removed=retention_report.total_removed, now=moment)
                ticks += 1
                consecutive_crashes = 0
                if self._stop_token.wait(self._idle_sleep_seconds):
                    break
            except Exception as exc:  # noqa: BLE001
                crashes += 1
                consecutive_crashes += 1
                last_error = self._format_error(exc)
                if consecutive_crashes >= self._max_consecutive_crashes:
                    break
                if self._stop_token.wait(self._idle_sleep_seconds):
                    break
        return JanitorLoopReport(
            tenant_id=self._tenant_id,
            queue_name=self._queue_name,
            ticks=ticks,
            crashes=crashes,
            reclaimed_expired_claims=reclaimed_expired_claims,
            retained_removed=retained_removed,
            started_at=started_at,
            stopped_at=normalize_now(),
            last_error=last_error,
        )

    @staticmethod
    def _format_error(exc: Exception) -> str:
        message = str(exc).strip()
        return f"{type(exc).__name__}:{message}" if message else type(exc).__name__


__all__ = [
    "CANON_RUNTIME_QUEUE_JANITOR_LOOP",
    "JanitorLoopReport",
    "JanitorLoopTick",
    "JobJanitorLoop",
]
