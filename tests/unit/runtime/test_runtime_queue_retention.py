from __future__ import annotations

from datetime import timedelta

from runtime.queue.job_contract import JobDispatchRequest, JobState, utc_now
from runtime.queue.job_store import InMemoryJobStore
from runtime.queue.job_store_sqlite import SqliteJobStore
from runtime.queue.queue_retention import QueueRetentionManager, QueueRetentionPolicy


def _request(job_id: str) -> JobDispatchRequest:
    return JobDispatchRequest(
        tenant_id="tenant-1",
        job_id=job_id,
        queue_name="email",
        job_type="send_email",
        payload={"recipient": f"{job_id}@example.com"},
        dedupe_key=f"dedupe-{job_id}",
    )


def _seed_terminal_jobs(store, now):
    job1 = store.put(_request("job-s").to_record(now=now))
    claim1 = store.claim(tenant_id="tenant-1", job_id=job1.job_id, owner_id="worker-a", lease_seconds=30, now=now)
    store.mark_succeeded(tenant_id="tenant-1", job_id=job1.job_id, owner_id="worker-a", fencing_token=claim1.lease.fencing_token, now=now)

    job2 = store.put(_request("job-f").to_record(now=now))
    claim2 = store.claim(tenant_id="tenant-1", job_id=job2.job_id, owner_id="worker-a", lease_seconds=30, now=now)
    store.mark_failed(tenant_id="tenant-1", job_id=job2.job_id, error="boom", owner_id="worker-a", fencing_token=claim2.lease.fencing_token, now=now)


def test_inmemory_retention_prunes_old_terminal_jobs() -> None:
    now = utc_now()
    store = InMemoryJobStore()
    _seed_terminal_jobs(store, now - timedelta(seconds=10))
    manager = QueueRetentionManager(store=store, policy=QueueRetentionPolicy(succeeded_ttl_seconds=1, failed_ttl_seconds=1, dead_letter_ttl_seconds=999, cancelled_ttl_seconds=999, batch_limit=100))
    report = manager.prune(tenant_id="tenant-1", queue_name="email", now=now)
    assert report.total_removed == 2
    assert store.count(tenant_id="tenant-1", queue_name="email") == 0


def test_sqlite_retention_prunes_old_terminal_jobs(tmp_path) -> None:
    now = utc_now()
    store = SqliteJobStore(tmp_path / "jobs.sqlite3")
    _seed_terminal_jobs(store, now - timedelta(seconds=10))
    manager = QueueRetentionManager(store=store, policy=QueueRetentionPolicy(succeeded_ttl_seconds=1, failed_ttl_seconds=1, dead_letter_ttl_seconds=999, cancelled_ttl_seconds=999, batch_limit=100))
    report = manager.prune(tenant_id="tenant-1", queue_name="email", now=now)
    assert report.total_removed == 2
    assert store.count(tenant_id="tenant-1", queue_name="email") == 0
    store.close()
