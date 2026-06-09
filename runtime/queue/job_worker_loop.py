from __future__ import annotations

"""Polling loop for runtime queue workers.

This layer repeatedly invokes the canonical worker tick.
It is intentionally operational-only and must not add planning logic.
"""

from dataclasses import dataclass
from datetime import datetime

from runtime.queue.job_contract import normalize_now
from runtime.queue.job_stop_token import JobStopToken
from runtime.queue.job_worker import JobWorker, WorkerTickReport
from runtime.queue.queue_observability import QueueObservabilityRegistry

CANON_RUNTIME_QUEUE_WORKER_LOOP = True


@dataclass(frozen=True)
class WorkerLoopReport:
    worker_id: str
    queue_name: str
    ticks: int = 0
    crashes: int = 0
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    last_error: str | None = None


class JobWorkerLoop:
    def __init__(
        self,
        *,
        worker: JobWorker,
        queue_name: str,
        tenant_id: str,
        stop_token: JobStopToken | None = None,
        observability: QueueObservabilityRegistry | None = None,
        idle_sleep_seconds: float = 0.2,
        crash_sleep_seconds: float = 0.5,
        max_consecutive_crashes: int = 3,
    ) -> None:
        self._worker = worker
        self._queue_name = str(queue_name).strip()
        self._tenant_id = str(tenant_id).strip()
        if not self._queue_name:
            raise ValueError("queue_name is required")
        if not self._tenant_id:
            raise ValueError("tenant_id is required")
        self._stop_token = stop_token or JobStopToken()
        self._observability = observability
        self._idle_sleep_seconds = max(0.01, float(idle_sleep_seconds))
        self._crash_sleep_seconds = max(0.01, float(crash_sleep_seconds))
        self._max_consecutive_crashes = max(1, int(max_consecutive_crashes))

    @property
    def stop_token(self) -> JobStopToken:
        return self._stop_token

    def run(self, *, max_ticks: int | None = None, now: datetime | None = None) -> WorkerLoopReport:
        started_at = normalize_now(now)
        ticks = 0
        crashes = 0
        consecutive_crashes = 0
        last_error: str | None = None

        while not self._stop_token.is_stop_requested():
            if max_ticks is not None and ticks >= int(max_ticks):
                break
            try:
                report = self._worker.tick(
                    tenant_id=self._tenant_id,
                    queue_name=self._queue_name,
                    now=normalize_now(),
                )
                ticks += 1
                consecutive_crashes = 0
                if self._observability is not None:
                    self._observability.record_worker_tick(report, now=normalize_now())
                self._sleep_after_tick(report)
            except Exception as exc:
                crashes += 1
                consecutive_crashes += 1
                last_error = self._format_error(exc)
                if self._observability is not None:
                    self._observability.record_worker_crash(
                        worker_id=self._worker.worker_id,
                        queue_name=self._queue_name,
                        error=last_error,
                        now=normalize_now(),
                    )
                if consecutive_crashes >= self._max_consecutive_crashes:
                    break
                if self._stop_token.wait(self._crash_sleep_seconds):
                    break

        stopped_at = normalize_now()
        if self._observability is not None and self._stop_token.is_stop_requested():
            self._observability.record_stop_requested(
                worker_id=self._worker.worker_id,
                queue_name=self._queue_name,
                now=stopped_at,
            )
        return WorkerLoopReport(
            worker_id=self._worker.worker_id,
            queue_name=self._queue_name,
            ticks=ticks,
            crashes=crashes,
            started_at=started_at,
            stopped_at=stopped_at,
            last_error=last_error,
        )

    def _sleep_after_tick(self, report: WorkerTickReport) -> None:
        if report.claimed > 0:
            return
        self._stop_token.wait(self._idle_sleep_seconds)

    @staticmethod
    def _format_error(exc: Exception) -> str:
        message = str(exc).strip()
        return f"{type(exc).__name__}:{message}" if message else type(exc).__name__


__all__ = [
    "CANON_RUNTIME_QUEUE_WORKER_LOOP",
    "JobWorkerLoop",
    "WorkerLoopReport",
]
