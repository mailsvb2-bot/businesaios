from __future__ import annotations

from datetime import timedelta
from multiprocessing import get_context
from pathlib import Path

from runtime.queue.job_contract import JobDispatchRequest, utc_now
from runtime.queue.job_store_sqlite import SqliteJobStore

CTX = get_context("fork")


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


def _claim_once(db_path: str, owner_id: str, out_queue) -> None:
    store = SqliteJobStore(Path(db_path))
    try:
        claimed = store.claim(tenant_id="tenant-1", job_id="job-1", owner_id=owner_id, lease_seconds=30, now=utc_now())
        out_queue.put((owner_id, claimed.job_id if claimed is not None else None, claimed.lease.fencing_token if claimed and claimed.lease else None))
    finally:
        store.close()


def _stale_finalize_attempt(db_path: str, owner_id: str, fencing_token: int, out_queue) -> None:
    store = SqliteJobStore(Path(db_path))
    try:
        try:
            store.mark_succeeded(
                tenant_id="tenant-1",
                job_id="job-1",
                owner_id=owner_id,
                fencing_token=fencing_token,
                now=utc_now(),
            )
            out_queue.put("unexpected_success")
        except Exception as exc:  # noqa: BLE001 - this is an assertion transport helper
            out_queue.put(f"{type(exc).__name__}:{exc}")
    finally:
        store.close()


def test_only_one_process_can_claim_single_due_job(tmp_path) -> None:
    db_path = tmp_path / "jobs.sqlite3"
    store = SqliteJobStore(db_path)
    store.put(_request().to_record(now=utc_now()))
    store.close()

    out_queue = CTX.Queue()
    workers = [
        CTX.Process(target=_claim_once, args=(str(db_path), f"proc-{index}", out_queue))
        for index in range(2)
    ]
    for proc in workers:
        proc.start()
    for proc in workers:
        proc.join(timeout=10)
        assert proc.exitcode == 0

    results = [out_queue.get(timeout=5) for _ in range(2)]
    winners = [item for item in results if item[1] == "job-1"]
    losers = [item for item in results if item[1] is None]
    assert len(winners) == 1
    assert len(losers) == 1
    assert winners[0][2] == 1


def test_stale_process_cannot_finalize_after_reclaim_even_with_same_owner_id(tmp_path) -> None:
    db_path = tmp_path / "jobs.sqlite3"
    store = SqliteJobStore(db_path)
    now = utc_now()
    store.put(_request().to_record(now=now))
    first = store.claim(tenant_id="tenant-1", job_id="job-1", owner_id="shared-owner", lease_seconds=1, now=now)
    assert first is not None and first.lease is not None
    store.reap_expired_claims(tenant_id="tenant-1", queue_name="email", now=now + timedelta(seconds=2))
    reclaimed = store.claim(tenant_id="tenant-1", job_id="job-1", owner_id="shared-owner", lease_seconds=30, now=now + timedelta(seconds=2))
    assert reclaimed is not None and reclaimed.lease is not None
    assert reclaimed.lease.fencing_token == first.lease.fencing_token + 1
    store.close()

    out_queue = CTX.Queue()
    proc = CTX.Process(target=_stale_finalize_attempt, args=(str(db_path), "shared-owner", first.lease.fencing_token, out_queue))
    proc.start()
    proc.join(timeout=10)
    assert proc.exitcode == 0
    message = out_queue.get(timeout=5)
    assert "fencing token mismatch" in message

    check_store = SqliteJobStore(db_path)
    current = check_store.get(tenant_id="tenant-1", job_id="job-1")
    assert current is not None and current.state.value == "claimed"
    assert current.lease is not None and current.lease.fencing_token == reclaimed.lease.fencing_token
    check_store.close()
