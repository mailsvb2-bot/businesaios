from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from runtime.queue._sqlite_job_store_codec import from_iso_datetime, iso_datetime, write_full_row
from runtime.queue.job_contract import JobState, normalize_now


def release_claim_sqlite(*, db, fetch_job, tenant_id: str, job_id: str, owner_id: str, fencing_token: int | None = None, now=None):
    moment = normalize_now(now)
    current = fetch_job(db, tenant_id=tenant_id, job_id=job_id)
    if current is None:
        raise KeyError(f"job not found: tenant_id={tenant_id} job_id={job_id}")
    if current.state is not JobState.CLAIMED or current.lease is None or current.lease.owner_id != owner_id:
        return None
    if fencing_token is not None and current.lease.fencing_token != fencing_token:
        return None
    db.execute(
        """
        UPDATE runtime_queue_jobs
        SET state = ?, updated_at = ?, lease_owner_id = NULL, lease_fencing_token = 0, lease_claimed_at = NULL, lease_expires_at = NULL
        WHERE tenant_id = ? AND job_id = ?
        """,
        (JobState.PENDING.value, iso_datetime(max(moment, current.updated_at)), tenant_id, job_id),
    )
    released = fetch_job(db, tenant_id=tenant_id, job_id=job_id)
    assert released is not None
    return released


def reap_expired_claims_sqlite(*, db, tenant_id: str, queue_name: str, now=None) -> int:
    moment = normalize_now(now)
    rows = db.execute(
        """
        SELECT job_id, updated_at FROM runtime_queue_jobs
        WHERE tenant_id = ? AND queue_name = ? AND state = ? AND lease_expires_at IS NOT NULL AND lease_expires_at <= ?
        """,
        (tenant_id, queue_name, JobState.CLAIMED.value, iso_datetime(moment)),
    ).fetchall()
    for row in rows:
        db.execute(
            """
            UPDATE runtime_queue_jobs
            SET state = ?, updated_at = ?, lease_owner_id = NULL, lease_fencing_token = 0, lease_claimed_at = NULL, lease_expires_at = NULL
            WHERE tenant_id = ? AND job_id = ?
            """,
            (JobState.PENDING.value, iso_datetime(max(moment, from_iso_datetime(row["updated_at"]) or moment)), tenant_id, str(row["job_id"])),
        )
    return len(rows)


def reschedule_claimed_job_sqlite(*, db, require_transitionable, fetch_job, tenant_id: str, job_id: str, delay_seconds: int, error: str, owner_id: str | None = None, fencing_token: int | None = None, now=None):
    moment = normalize_now(now)
    current = require_transitionable(
        db,
        tenant_id=tenant_id,
        job_id=job_id,
        allowed_from=(JobState.CLAIMED,),
        owner_id=owner_id,
        fencing_token=fencing_token,
    )
    updated = replace(
        current,
        state=JobState.PENDING,
        lease=None,
        last_error=str(error),
        run_at=moment + timedelta(seconds=max(0, int(delay_seconds))),
        updated_at=max(moment, current.updated_at),
    )
    write_full_row(db, updated)
    saved = fetch_job(db, tenant_id=tenant_id, job_id=job_id)
    assert saved is not None
    return saved
