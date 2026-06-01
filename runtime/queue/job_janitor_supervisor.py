from __future__ import annotations

"""Supervisor for queue janitor loops.

Operational only. This owns janitor thread lifecycle, not job decisions.
"""

from dataclasses import dataclass
from threading import Lock, Thread

from runtime.queue.job_contract import normalize_now
from runtime.queue.job_janitor_loop import JanitorLoopReport, JobJanitorLoop
from runtime.queue.job_stop_token import JobStopToken

CANON_RUNTIME_QUEUE_JANITOR_SUPERVISOR = True


@dataclass(frozen=True)
class JanitorHandle:
    queue_name: str
    tenant_id: str
    thread_name: str
    is_alive: bool
    started_at: object | None = None
    report: JanitorLoopReport | None = None


class JobJanitorSupervisor:
    def __init__(self, *, janitor_loop: JobJanitorLoop, max_restart_attempts: int = 1) -> None:
        self._loop = janitor_loop
        self._max_restart_attempts = max(0, int(max_restart_attempts))
        self._lock = Lock()
        self._thread: Thread | None = None
        self._report: JanitorLoopReport | None = None
        self._started_at = None

    @property
    def stop_token(self) -> JobStopToken:
        return self._loop.stop_token

    def start(self) -> None:
        with self._lock:
            if self._thread is not None:
                raise RuntimeError("janitor supervisor already started")
            self._started_at = normalize_now()
            self._thread = Thread(target=self._run_loop, name=f"queue-janitor-supervisor-{self._loop._queue_name}", daemon=True)
            self._thread.start()

    def request_stop(self, *, reason: str = "janitor_supervisor_stop") -> None:
        self._loop.stop_token.request_stop(reason=reason, now=normalize_now())

    def join(self, *, timeout_seconds: float = 10.0) -> JanitorLoopReport | None:
        with self._lock:
            thread = self._thread
        if thread is not None:
            thread.join(timeout=max(0.0, float(timeout_seconds)))
        with self._lock:
            return self._report

    def snapshot(self) -> JanitorHandle:
        with self._lock:
            return JanitorHandle(
                queue_name=self._loop._queue_name,
                tenant_id=self._loop._tenant_id,
                thread_name=(self._thread.name if self._thread is not None else f"queue-janitor-supervisor-{self._loop._queue_name}"),
                is_alive=(self._thread.is_alive() if self._thread is not None else False),
                started_at=self._started_at,
                report=self._report,
            )

    def _run_loop(self) -> None:
        attempts = 0
        final_report = None
        while True:
            report = self._loop.run()
            final_report = report
            if report.crashes <= 0 or attempts >= self._max_restart_attempts or self._loop.stop_token.is_stop_requested():
                break
            attempts += 1
        with self._lock:
            self._report = final_report


__all__ = [
    "CANON_RUNTIME_QUEUE_JANITOR_SUPERVISOR",
    "JanitorHandle",
    "JobJanitorSupervisor",
]
