from __future__ import annotations

"""Runtime queue worker.

The worker executes already-decided jobs with an injected runner.
It must not decide business intent on its own.
"""

from contextlib import contextmanager
from core.tenancy.normalization import require_tenant_id
from dataclasses import dataclass
from datetime import datetime
from threading import Event, Thread
from typing import Any, Callable, Iterator, Mapping

from runtime.queue.job_contract import JobRecord, JobResult, normalize_now
from runtime.queue.job_dead_letter_store import DeadLetterRecord, JobDeadLetterStore
from runtime.queue.job_lease_manager import JobLeaseManager
from runtime.queue.job_retry_policy import JobRetryPolicy
from runtime.queue.job_scheduler import JobScheduler
from runtime.queue.job_fencing import build_process_scoped_worker_id
from runtime.queue.job_store import JobStore


CANON_RUNTIME_QUEUE_WORKER = True

JobRunner = Callable[[JobRecord], Any]


@dataclass(frozen=True)
class WorkerTickReport:
    worker_id: str
    queue_name: str
    claimed: int = 0
    skipped: int = 0
    succeeded: int = 0
    failed: int = 0
    retried: int = 0
    dead_lettered: int = 0
    reclaimed_expired_claims: int = 0


class LeaseLostError(RuntimeError):
    """Raised when a worker can no longer prove ownership of a claimed job."""


class JobWorker:
    def __init__(
        self,
        *,
        worker_id: str,
        store: JobStore,
        scheduler: JobScheduler,
        runner: JobRunner,
        retry_policy: JobRetryPolicy | None = None,
        dead_letter_store: JobDeadLetterStore | None = None,
        lease_manager: JobLeaseManager | None = None,
        lease_seconds: int = 60,
    ) -> None:
        worker = str(worker_id).strip()
        if not worker:
            raise ValueError("worker_id is required")
        if "@" not in worker or ":pid=" not in worker:
            worker = build_process_scoped_worker_id(prefix=worker)
        self._worker_id = worker
        self._store = store
        self._scheduler = scheduler
        self._runner = runner
        self._retry_policy = retry_policy or JobRetryPolicy()
        self._dead_letter_store = dead_letter_store
        self._lease_manager = lease_manager or JobLeaseManager(store=store, default_owner_id=worker)
        self._lease_seconds = max(5, int(lease_seconds))

    @property
    def worker_id(self) -> str:
        return self._worker_id

    @contextmanager
    def _lease_heartbeat(self, job: JobRecord) -> Iterator[None]:
        current = self._store.get(tenant_id=job.tenant_id, job_id=job.job_id) or job
        window = self._lease_manager.visibility_window_for(job=current)
        stop_event = Event()
        lease_lost = Event()

        def _loop() -> None:
            while not stop_event.wait(float(window.heartbeat_seconds)):
                renewed = self._lease_manager.heartbeat(
                    tenant_id=job.tenant_id,
                    job_id=job.job_id,
                    owner_id=self._worker_id,
                )
                if renewed is None:
                    lease_lost.set()
                    stop_event.set()
                    return

        thread = Thread(target=_loop, name=f"queue-heartbeat-{self._worker_id}-{job.job_id}", daemon=True)
        thread.start()
        try:
            yield
        finally:
            stop_event.set()
            thread.join(timeout=max(1.0, float(window.heartbeat_seconds) + 1.0))
            if lease_lost.is_set():
                raise LeaseLostError(f"lease lost while executing job {job.job_id}")

    def tick(self, *, tenant_id: str, queue_name: str, now: datetime | None = None) -> WorkerTickReport:
        moment = normalize_now(now)
        normalized_tenant_id = require_tenant_id(tenant_id)
        normalized_queue_name = str(queue_name or '').strip()
        if not normalized_queue_name:
            raise ValueError('queue_name is required')
        batch = self._scheduler.select_due_jobs(tenant_id=normalized_tenant_id, queue_name=normalized_queue_name, now=moment)
        report = WorkerTickReport(worker_id=self._worker_id, queue_name=normalized_queue_name, reclaimed_expired_claims=batch.reclaimed_expired_claims)

        for candidate in batch.jobs:
            claimed = self._lease_manager.claim(
                tenant_id=normalized_tenant_id,
                job_id=candidate.job_id,
                owner_id=self._worker_id,
                lease_seconds=self._lease_seconds,
                now=moment,
            )
            if claimed is None:
                report = self._replace(report, skipped=report.skipped + 1)
                continue
            self._scheduler.commit_claimed_job(job=claimed, now=moment)
            report = self._replace(report, claimed=report.claimed + 1)
            report = self._run_claimed(tenant_id=claimed.tenant_id, job=claimed, report=report, now=normalize_now())

        return report

    def _run_claimed(self, *, tenant_id: str, job: JobRecord, report: WorkerTickReport, now: datetime) -> WorkerTickReport:
        try:
            with self._lease_heartbeat(job):
                outcome = self._runner(job)
            result = self._normalize_result(job=job, outcome=outcome)
            if result.ok:
                completed_at = normalize_now()
                self._store.mark_succeeded(tenant_id=tenant_id, job_id=job.job_id, owner_id=self._worker_id, fencing_token=(job.lease.fencing_token if job.lease is not None else None), now=completed_at)
                return self._replace(report, succeeded=report.succeeded + 1)
            synthetic_error = result.error or result.status or "runner_reported_failure"
            return self._handle_failure(tenant_id=tenant_id, job=job, report=report, exc=RuntimeError(synthetic_error), result=result, now=now)
        except LeaseLostError:
            return self._replace(report, skipped=report.skipped + 1)
        except Exception as exc:
            return self._handle_failure(tenant_id=tenant_id, job=job, report=report, exc=exc, result=None, now=now)

    def _handle_failure(self, *, tenant_id: str, job: JobRecord, report: WorkerTickReport, exc: Exception, result: JobResult | None, now: datetime) -> WorkerTickReport:
        failure_moment = normalize_now(now)
        error_text = self._format_error(exc)
        decision = self._retry_policy.classify(job=job, error=exc)
        retry_delay = result.retry_delay_seconds if result and result.retry_delay_seconds is not None else decision.delay_seconds
        if decision.move_to_dead_letter:
            self._store.mark_dead_letter(tenant_id=tenant_id, job_id=job.job_id, error=error_text, owner_id=self._worker_id, fencing_token=(job.lease.fencing_token if job.lease is not None else None), now=failure_moment)
            self._record_dead_letter(job=job, error=error_text, reason=decision.reason, now=failure_moment)
            return self._replace(report, dead_lettered=report.dead_lettered + 1)
        if decision.should_retry:
            self._store.reschedule(tenant_id=tenant_id, job_id=job.job_id, delay_seconds=retry_delay, error=error_text, owner_id=self._worker_id, fencing_token=(job.lease.fencing_token if job.lease is not None else None), now=failure_moment)
            return self._replace(report, retried=report.retried + 1)
        self._store.mark_failed(tenant_id=tenant_id, job_id=job.job_id, error=error_text, owner_id=self._worker_id, fencing_token=(job.lease.fencing_token if job.lease is not None else None), now=failure_moment)
        return self._replace(report, failed=report.failed + 1)

    def _normalize_result(self, *, job: JobRecord, outcome: Any) -> JobResult:
        if isinstance(outcome, JobResult):
            return outcome
        if outcome is None:
            return JobResult(ok=True, status="ok", job_id=job.job_id, tenant_id=job.tenant_id, attempts=job.attempts, output={})
        if isinstance(outcome, Mapping):
            ok = bool(outcome.get("ok", True))
            status = str(outcome.get("status") or ("ok" if ok else "error"))
            error = outcome.get("error")
            retry_delay_seconds = outcome.get("retry_delay_seconds")
            raw_output = outcome.get("output")
            output = raw_output if isinstance(raw_output, dict) else {k: v for k, v in outcome.items() if k not in {"ok", "status", "error", "retry_delay_seconds", "output"}}
            return JobResult(ok=ok, status=status, job_id=job.job_id, tenant_id=job.tenant_id, attempts=job.attempts, output=output, error=None if error is None else str(error), retry_delay_seconds=retry_delay_seconds)
        return JobResult(ok=True, status="ok", job_id=job.job_id, tenant_id=job.tenant_id, attempts=job.attempts, output={"result": outcome})

    @staticmethod
    def _format_error(exc: Exception) -> str:
        message = str(exc).strip()
        return f"{type(exc).__name__}:{message}" if message else type(exc).__name__

    def _record_dead_letter(self, *, job: JobRecord, error: str, reason: str, now: datetime) -> None:
        if self._dead_letter_store is None:
            return
        self._dead_letter_store.put(DeadLetterRecord(tenant_id=job.tenant_id, job_id=job.job_id, queue_name=job.queue_name, job_type=job.job_type, reason=reason, failed_at=now, attempts=int(job.attempts), last_error=str(error), original_job=job))

    @staticmethod
    def _replace(report: WorkerTickReport, **changes: int) -> WorkerTickReport:
        data = report.__dict__.copy()
        data.update(changes)
        return WorkerTickReport(**data)


__all__ = [
    "CANON_RUNTIME_QUEUE_WORKER",
    "JobRunner",
    "JobWorker",
    "LeaseLostError",
    "WorkerTickReport",
]
