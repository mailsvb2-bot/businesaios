from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from runtime.queue.job_contract import JobDispatchRequest, JobState, utc_now
from runtime.queue.job_retry_policy import JobRetryPolicy
from runtime.queue.job_scheduler import JobScheduler
from runtime.queue.job_store_sqlite import SqliteJobStore
from runtime.queue.job_worker import JobWorker


def _request(index: int) -> JobDispatchRequest:
    return JobDispatchRequest(tenant_id="tenant-1", job_id=f"job-{index}", queue_name="email", job_type="send_email", payload={"recipient": f"u{index}@example.com"}, dedupe_key=f"dedupe-{index}")


def test_sqlite_queue_soak_completes_jobs_without_duplicates(tmp_path) -> None:
    total_jobs = 40
    store = SqliteJobStore(tmp_path / "jobs.sqlite3")
    now = utc_now()
    for index in range(total_jobs):
        store.put(_request(index).to_record(now=now))

    seen: list[str] = []

    def runner(job):
        seen.append(job.job_id)
        return {"ok": True}

    workers = [
        JobWorker(worker_id=f"worker-{i}", store=store, scheduler=JobScheduler(store=store), runner=runner, retry_policy=JobRetryPolicy(base_delay_seconds=1, jitter_seconds=0), lease_seconds=2)
        for i in range(4)
    ]

    def pump(worker):
        local_succeeded = 0
        for _ in range(total_jobs):
            report = worker.tick(tenant_id="tenant-1", queue_name="email", now=utc_now())
            local_succeeded += report.succeeded
        return local_succeeded

    with ThreadPoolExecutor(max_workers=4) as pool:
        counts = list(pool.map(pump, workers))

    assert sum(counts) == total_jobs
    assert len(set(seen)) == total_jobs
    assert store.count(tenant_id="tenant-1", queue_name="email") == total_jobs
    assert store.count(tenant_id="tenant-1", queue_name="email", state=JobState.SUCCEEDED) == total_jobs
    store.close()
