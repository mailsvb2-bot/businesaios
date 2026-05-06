from __future__ import annotations

from datetime import datetime, timedelta
from multiprocessing import get_context
from pathlib import Path
import os

from runtime.queue.job_contract import JobDispatchRequest, utc_now
from runtime.queue.job_janitor import JobQueueJanitor
from runtime.queue.job_store_sqlite import SqliteJobStore


CTX = get_context("fork")


def _request() -> JobDispatchRequest:
    return JobDispatchRequest(tenant_id="tenant-1", job_id="job-1", queue_name="email", job_type="send_email", payload={"recipient": "a@example.com"}, dedupe_key="dedupe-1")


def _claim_and_crash(db_path: str, claim_at_iso: str) -> None:
    store = SqliteJobStore(Path(db_path))
    claim = store.claim(tenant_id="tenant-1", job_id="job-1", owner_id="worker-a", lease_seconds=1, now=datetime.fromisoformat(claim_at_iso))
    assert claim is not None
    os._exit(137)


def test_crashed_process_claim_is_reclaimed_and_job_can_complete(tmp_path) -> None:
    db_path = tmp_path / "jobs.sqlite3"
    store = SqliteJobStore(db_path)
    now = utc_now()
    store.put(_request().to_record(now=now))
    store.close()

    proc = CTX.Process(target=_claim_and_crash, args=(str(db_path), now.isoformat()))
    proc.start()
    proc.join(timeout=10)
    assert proc.exitcode == 137

    check = SqliteJobStore(db_path)
    janitor = JobQueueJanitor(store=check)
    report = janitor.tick(tenant_id="tenant-1", queue_name="email", now=now + timedelta(seconds=2))
    assert report.reclaimed_expired_claims == 1
    reclaimed = check.claim(tenant_id="tenant-1", job_id="job-1", owner_id="worker-b", lease_seconds=30, now=now + timedelta(seconds=2))
    assert reclaimed is not None and reclaimed.lease is not None
    check.mark_succeeded(tenant_id="tenant-1", job_id="job-1", owner_id="worker-b", fencing_token=reclaimed.lease.fencing_token, now=now + timedelta(seconds=3))
    saved = check.get(tenant_id="tenant-1", job_id="job-1")
    assert saved is not None and saved.state.value == "succeeded"
    check.close()
