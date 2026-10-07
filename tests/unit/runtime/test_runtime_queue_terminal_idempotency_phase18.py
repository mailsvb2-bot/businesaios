from __future__ import annotations

from datetime import timedelta

import pytest

from runtime.queue.job_contract import JobDispatchRequest, utc_now
from runtime.queue.job_store import InMemoryJobStore
from runtime.queue.job_store_sqlite import SqliteJobStore


def _exercise_idempotent_success(store) -> None:
    now = utc_now()
    store.put(JobDispatchRequest(
        tenant_id="tenant-a",
        job_id="job-1",
        queue_name="ops",
        job_type="demo",
        payload={"x": 1},
        dedupe_key="d-1",
    ).to_record(now=now))
    claimed = store.claim(
        tenant_id="tenant-a",
        job_id="job-1",
        owner_id="worker-a",
        lease_seconds=30,
        now=now,
    )
    assert claimed is not None and claimed.lease is not None
    first = store.mark_succeeded(
        tenant_id="tenant-a",
        job_id="job-1",
        owner_id="worker-a",
        fencing_token=claimed.lease.fencing_token,
        now=now + timedelta(seconds=1),
    )
    replay = store.mark_succeeded(
        tenant_id="tenant-a",
        job_id="job-1",
        owner_id="worker-a",
        fencing_token=claimed.lease.fencing_token,
        now=now + timedelta(seconds=2),
    )
    assert replay == first
    assert replay.state.value == "succeeded"


def test_inmemory_terminal_success_is_idempotent() -> None:
    _exercise_idempotent_success(InMemoryJobStore())


def test_sqlite_terminal_success_is_idempotent(tmp_path) -> None:
    store = SqliteJobStore(tmp_path / "jobs.sqlite3")
    _exercise_idempotent_success(store)
    store.close()


def test_sqlite_stale_fencing_after_reclaim_still_fails(tmp_path) -> None:
    store = SqliteJobStore(tmp_path / "jobs.sqlite3")
    now = utc_now()
    store.put(JobDispatchRequest(
        tenant_id="tenant-a",
        job_id="job-1",
        queue_name="ops",
        job_type="demo",
        payload={"x": 1},
        dedupe_key="d-1",
    ).to_record(now=now))
    first = store.claim(tenant_id="tenant-a", job_id="job-1", owner_id="worker-a", lease_seconds=1, now=now)
    assert first is not None and first.lease is not None
    store.reap_expired_claims(tenant_id="tenant-a", queue_name="ops", now=now + timedelta(seconds=2))
    second = store.claim(tenant_id="tenant-a", job_id="job-1", owner_id="worker-a", lease_seconds=30, now=now + timedelta(seconds=2))
    assert second is not None and second.lease is not None

    with pytest.raises(ValueError, match="fencing token mismatch"):
        store.mark_succeeded(
            tenant_id="tenant-a",
            job_id="job-1",
            owner_id="worker-a",
            fencing_token=first.lease.fencing_token,
            now=now + timedelta(seconds=3),
        )
    store.close()
