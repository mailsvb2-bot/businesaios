from __future__ import annotations

from datetime import timedelta
from time import sleep

from runtime.queue.job_contract import JobDispatchRequest, utc_now
from runtime.queue.job_retry_policy import JobRetryPolicy
from runtime.queue.job_scheduler import JobScheduler
from runtime.queue.job_store_sqlite import SqliteJobStore
from runtime.queue.job_worker import JobWorker


def _request(**overrides: object) -> JobDispatchRequest:
    data = {
        "tenant_id": "tenant-1",
        "job_id": "job-1",
        "queue_name": "email",
        "job_type": "send_email",
        "payload": {"recipient": "a@example.com"},
        "dedupe_key": "dedupe-1",
    }
    data.update(overrides)
    return JobDispatchRequest(**data)


def test_sqlite_store_rejects_terminal_transition_from_wrong_owner(tmp_path) -> None:
    store = SqliteJobStore(tmp_path / "jobs.sqlite3")
    now = utc_now()
    store.put(_request().to_record(now=now))
    claimed = store.claim(tenant_id="tenant-1", job_id="job-1", owner_id="worker-a", lease_seconds=60, now=now)
    assert claimed is not None

    try:
        store.mark_succeeded(tenant_id="tenant-1", job_id="job-1", owner_id="worker-b", now=now + timedelta(seconds=1))
    except ValueError as exc:
        assert "lease owner mismatch" in str(exc)
    else:
        raise AssertionError("expected owner-guarded transition to fail")


def test_worker_heartbeats_long_running_job_and_completes_once(tmp_path) -> None:
    store = SqliteJobStore(tmp_path / "jobs.sqlite3")
    now = utc_now()
    store.put(_request().to_record(now=now))

    calls: list[str] = []

    def runner(job):
        calls.append(job.job_id)
        sleep(0.3)
        return {"ok": True}

    worker = JobWorker(
        worker_id="worker-a",
        store=store,
        scheduler=JobScheduler(store=store),
        runner=runner,
        retry_policy=JobRetryPolicy(base_delay_seconds=1, jitter_seconds=0),
        lease_seconds=1,
    )

    report = worker.tick(tenant_id="tenant-1", queue_name="email", now=now)
    assert report.succeeded == 1
    assert calls == ["job-1"]
    saved = store.get(tenant_id="tenant-1", job_id="job-1")
    assert saved is not None
    assert saved.state.value == "succeeded"
