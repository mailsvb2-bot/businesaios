from __future__ import annotations

from datetime import timedelta

from runtime.queue.job_contract import JobDispatchRequest, utc_now
from runtime.queue.job_store_sqlite import SqliteJobStore


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


def test_sqlite_store_renew_lease_extends_from_current_expiry(tmp_path) -> None:
    store = SqliteJobStore(tmp_path / "jobs.sqlite3")
    now = utc_now()
    store.put(_request().to_record(now=now))
    claimed = store.claim(tenant_id="tenant-1", job_id="job-1", owner_id="w1", lease_seconds=30, now=now)
    assert claimed is not None

    renewed = store.renew_lease(
        tenant_id="tenant-1",
        job_id="job-1",
        owner_id="w1",
        lease_seconds=15,
        now=now + timedelta(seconds=5),
    )
    assert renewed is not None
    assert renewed.lease is not None
    assert renewed.lease.expires_at >= claimed.lease.expires_at + timedelta(seconds=15)


def test_sqlite_store_reclaims_expired_claims(tmp_path) -> None:
    store = SqliteJobStore(tmp_path / "jobs.sqlite3")
    now = utc_now()
    store.put(_request().to_record(now=now))
    claimed = store.claim(tenant_id="tenant-1", job_id="job-1", owner_id="w1", lease_seconds=1, now=now)
    assert claimed is not None

    changed = store.reap_expired_claims(tenant_id="tenant-1", queue_name="email", now=now + timedelta(seconds=2))
    assert changed == 1
    jobs = store.list_due(tenant_id="tenant-1", queue_name="email", limit=10, now=now + timedelta(seconds=2))
    assert [item.job_id for item in jobs] == ["job-1"]


def test_sqlite_store_dedupe_returns_existing_live_job(tmp_path) -> None:
    store = SqliteJobStore(tmp_path / "jobs.sqlite3")
    now = utc_now()
    first = store.put(_request().to_record(now=now))
    second = store.put(_request(job_id="job-2").to_record(now=now + timedelta(seconds=1)))
    assert second.job_id == first.job_id


def test_sqlite_store_claim_increments_fencing_token_on_reclaim(tmp_path) -> None:
    store = SqliteJobStore(tmp_path / "jobs.sqlite3")
    now = utc_now()
    store.put(_request().to_record(now=now))
    first = store.claim(tenant_id="tenant-1", job_id="job-1", owner_id="w1", lease_seconds=1, now=now)
    assert first is not None and first.lease is not None
    store.reap_expired_claims(tenant_id="tenant-1", queue_name="email", now=now + timedelta(seconds=2))
    second = store.claim(tenant_id="tenant-1", job_id="job-1", owner_id="w1", lease_seconds=30, now=now + timedelta(seconds=2))
    assert second is not None and second.lease is not None
    assert second.lease.fencing_token == first.lease.fencing_token + 1


def test_sqlite_store_rejects_stale_fencing_token_even_with_same_owner(tmp_path) -> None:
    store = SqliteJobStore(tmp_path / "jobs.sqlite3")
    now = utc_now()
    store.put(_request().to_record(now=now))
    first = store.claim(tenant_id="tenant-1", job_id="job-1", owner_id="w1", lease_seconds=1, now=now)
    assert first is not None and first.lease is not None
    store.reap_expired_claims(tenant_id="tenant-1", queue_name="email", now=now + timedelta(seconds=2))
    second = store.claim(tenant_id="tenant-1", job_id="job-1", owner_id="w1", lease_seconds=30, now=now + timedelta(seconds=2))
    assert second is not None and second.lease is not None
    try:
        store.mark_succeeded(
            tenant_id="tenant-1",
            job_id="job-1",
            owner_id="w1",
            fencing_token=first.lease.fencing_token,
            now=now + timedelta(seconds=3),
        )
    except ValueError as exc:
        assert "fencing token mismatch" in str(exc)
    else:
        raise AssertionError("expected stale fencing token to be rejected")
