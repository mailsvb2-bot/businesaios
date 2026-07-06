"""Supervisor for runtime queue worker loops.

This supervisor owns lifecycle only:
- start worker threads
- request graceful stop
- join worker threads
- expose health snapshots

It must not introduce queue policy or a second decision center.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from threading import Lock, Thread

from runtime.queue.job_contract import normalize_now
from runtime.queue.job_stop_token import JobStopToken
from runtime.queue.job_worker import JobWorker
from runtime.queue.job_worker_loop import JobWorkerLoop, WorkerLoopReport
from runtime.queue.queue_observability import QueueObservabilityRegistry, QueueObservabilitySnapshot

CANON_RUNTIME_QUEUE_WORKER_SUPERVISOR = True

@dataclass(frozen=True)
class WorkerHandle:
    worker_id: str
    queue_name: str
    tenant_id: str
    thread_name: str
    is_alive: bool
    started_at: object | None = None
    report: WorkerLoopReport | None = None


class JobWorkerSupervisor:
    def __init__(
        self,
        *,
        tenant_id: str,
        queue_name: str,
        workers: Iterable[JobWorker],
        observability: QueueObservabilityRegistry | None = None,
        idle_sleep_seconds: float = 0.2,
        max_restart_attempts_per_worker: int = 1,
    ) -> None:
        self._tenant_id = str(tenant_id).strip()
        self._queue_name = str(queue_name).strip()
        if not self._tenant_id:
            raise ValueError("tenant_id is required")
        if not self._queue_name:
            raise ValueError("queue_name is required")
        self._workers = tuple(workers)
        if not self._workers:
            raise ValueError("at least one worker is required")
        self._observability = observability or QueueObservabilityRegistry()
        self._idle_sleep_seconds = max(0.01, float(idle_sleep_seconds))
        self._max_restart_attempts_per_worker = max(0, int(max_restart_attempts_per_worker))
        self._lock = Lock()
        self._threads: dict[str, Thread] = {}
        self._tokens: dict[str, JobStopToken] = {}
        self._reports: dict[str, WorkerLoopReport] = {}
        self._started_at = None

    @property
    def observability(self) -> QueueObservabilityRegistry:
        return self._observability

    def start(self) -> None:
        with self._lock:
            if self._threads:
                raise RuntimeError("supervisor already started")
            self._started_at = normalize_now()
            for worker in self._workers:
                token = JobStopToken()
                loop = JobWorkerLoop(
                    worker=worker,
                    queue_name=self._queue_name,
                    tenant_id=self._tenant_id,
                    stop_token=token,
                    observability=self._observability,
                    idle_sleep_seconds=self._idle_sleep_seconds,
                )
                thread = Thread(
                    target=self._run_loop,
                    args=(worker.worker_id, loop),
                    name=f"queue-supervisor-{self._queue_name}-{worker.worker_id}",
                    daemon=True,
                )
                self._tokens[worker.worker_id] = token
                self._threads[worker.worker_id] = thread
                thread.start()

    def request_stop(self, *, reason: str = "supervisor_stop") -> None:
        with self._lock:
            for token in self._tokens.values():
                token.request_stop(reason=reason, now=normalize_now())

    def join(self, *, timeout_seconds: float = 10.0) -> tuple[WorkerLoopReport, ...]:
        deadline = None if timeout_seconds is None else (normalize_now().timestamp() + max(0.0, float(timeout_seconds)))
        with self._lock:
            threads = list(self._threads.items())
        for worker_id, thread in threads:
            remaining = None
            if deadline is not None:
                remaining = max(0.0, deadline - normalize_now().timestamp())
            thread.join(timeout=remaining)
        with self._lock:
            return tuple(self._reports[wid] for wid in sorted(self._reports))

    def snapshot(self) -> tuple[WorkerHandle, ...]:
        with self._lock:
            handles = []
            for worker in self._workers:
                thread = self._threads.get(worker.worker_id)
                handles.append(
                    WorkerHandle(
                        worker_id=worker.worker_id,
                        queue_name=self._queue_name,
                        tenant_id=self._tenant_id,
                        thread_name=thread.name if thread is not None else f"queue-supervisor-{self._queue_name}-{worker.worker_id}",
                        is_alive=thread.is_alive() if thread is not None else False,
                        started_at=self._started_at,
                        report=self._reports.get(worker.worker_id),
                    )
                )
            return tuple(handles)

    def observability_snapshot(self) -> QueueObservabilitySnapshot:
        return self._observability.snapshot()

    def _run_loop(self, worker_id: str, loop: JobWorkerLoop) -> None:
        attempts = 0
        final_report = None
        while True:
            report = loop.run()
            final_report = report
            if report.crashes <= 0 or attempts >= self._max_restart_attempts_per_worker or loop.stop_token.is_stop_requested():
                break
            attempts += 1
        with self._lock:
            self._reports[worker_id] = final_report


__all__ = [
    "CANON_RUNTIME_QUEUE_WORKER_SUPERVISOR",
    "JobWorkerSupervisor",
    "WorkerHandle",
]
