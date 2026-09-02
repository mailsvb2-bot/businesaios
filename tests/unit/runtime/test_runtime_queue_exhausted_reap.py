from __future__ import annotations

from datetime import timedelta

from runtime.queue import InMemoryJobStore, JobDispatchRequest, JobScheduler, JobState
from runtime.queue.job_contract import utc_now
from runtime.queue.job_store_sqlite import SqliteJobStore
from runtime.queue.job_worker import JobWorker


def _request(*, job_id: str = "job-1", max_attempts: int = 1) -> JobDispatchRequest:
    return JobDispatchRequest(
        tenant_id="tenant-1",
        job_id=job_id,
        queue_name="provider-sync",
        job_type="provider_sync",
        payload={"provider": "slack" if job_id == "job-1" else "discord"},
        dedupe_key=job_id,
        max_attempts=max_attempts,
    )


def test_inmemory_reaper_terminalizes_expired_exhausted_claim() -> None:
    store = InMemoryJobStore()
    now = utc_now()
    store.put(_request().to_record(now=now))
    claimed = store.claim(tenant_id="tenant-1", job_id="job-1", owner_id="worker-a", lease_seconds=1, now=now)
    assert claimed is not None and claimed.attempts == 1

    batch = JobScheduler(store=store).select_due_jobs(tenant_id="tenant-1", queue_name="provider-sync", now=now + timedelta(seconds=2))
    terminal = store.get(tenant_id="tenant-1", job_id="job-1")

    assert batch.reclaimed_expired_claims == 1
    assert batch.jobs == ()
    assert terminal is not None and terminal.state is JobState.DEAD_LETTER
    assert terminal.last_error == "expired_claim_attempts_exhausted_ambiguous_delivery"


def test_sqlite_reaper_terminalizes_one_shot_and_later_job_runs(tmp_path) -> None:
    store = SqliteJobStore(tmp_path / "jobs.sqlite3")
    now = utc_now()
    store.put(_request().to_record(now=now))
    store.put(_request(job_id="job-2").to_record(now=now))
    claimed = store.claim(tenant_id="tenant-1", job_id="job-1", owner_id="crashed-worker", lease_seconds=1, now=now)
    assert claimed is not None and claimed.attempts == 1

    executed: list[str] = []
    worker = JobWorker(
        worker_id="replacement",
        store=store,
        scheduler=JobScheduler(store=store),
        runner=lambda job: executed.append(job.job_id) or {"ok": True},
    )
    report = worker.tick(tenant_id="tenant-1", queue_name="provider-sync", now=now + timedelta(seconds=2))

    exhausted = store.get(tenant_id="tenant-1", job_id="job-1")
    completed = store.get(tenant_id="tenant-1", job_id="job-2")
    assert report.reclaimed_expired_claims == 1
    assert executed == ["job-2"]
    assert exhausted is not None and exhausted.state is JobState.DEAD_LETTER
    assert exhausted.last_error == "expired_claim_attempts_exhausted_ambiguous_delivery"
    assert completed is not None and completed.state is JobState.SUCCEEDED
    store.close()
