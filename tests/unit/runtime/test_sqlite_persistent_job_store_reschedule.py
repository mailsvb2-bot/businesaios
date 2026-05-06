from __future__ import annotations

from datetime import timedelta

from runtime.queue.job_contract import JobDispatchRequest, JobState, utc_now
from runtime.queue.job_store import SqlitePersistentJobStore


def test_sqlite_persistent_job_store_reschedule_matches_backend_contract(tmp_path) -> None:
    store = SqlitePersistentJobStore(path=tmp_path / "jobs.sqlite3")
    now = utc_now()
    job = store.put(
        JobDispatchRequest(
            tenant_id="tenant-a",
            job_id="job-1",
            queue_name="ops",
            job_type="demo",
            payload={"idx": 1},
            dedupe_key="dedupe-1",
        ).to_record(now=now)
    )
    claimed = store.claim(tenant_id=job.tenant_id, job_id=job.job_id, owner_id="worker-1", lease_seconds=30, now=now)
    assert claimed is not None

    rescheduled = store.reschedule(
        tenant_id=job.tenant_id,
        job_id=job.job_id,
        delay_seconds=9,
        error="timeout",
        owner_id="worker-1",
        fencing_token=claimed.lease.fencing_token if claimed.lease is not None else None,
        now=now,
    )

    assert rescheduled.state is JobState.PENDING
    assert rescheduled.lease is None
    assert rescheduled.last_error == "timeout"
    assert rescheduled.run_at == now + timedelta(seconds=9)
