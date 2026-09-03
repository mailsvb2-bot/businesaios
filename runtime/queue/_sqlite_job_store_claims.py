from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from runtime.queue._sqlite_job_store_codec import from_iso_datetime, iso_datetime, write_full_row
from runtime.queue.job_contract import JobClaimExpiryPolicy, JobState, normalize_now


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
        SELECT job_id, updated_at, attempts, max_attempts, claim_expiry_policy, last_error FROM runtime_queue_jobs
        WHERE tenant_id = ? AND queue_name = ? AND state = ? AND lease_expires_at IS NOT NULL AND lease_expires_at <= ?
        """,
        (tenant_id, queue_name, JobState.CLAIMED.value, iso_datetime(moment)),
    ).fetchall()
    for row in rows:
        ambiguous = str(row["claim_expiry_policy"]) == JobClaimExpiryPolicy.DEAD_LETTER_AMBIGUOUS.value
        exhausted = int(row["attempts"]) >= int(row["max_attempts"])
        dead_letter = ambiguous or exhausted
        db.execute(
            """
            UPDATE runtime_queue_jobs
            SET state = ?, updated_at = ?, last_error = ?, lease_owner_id = NULL, lease_fencing_token = 0, lease_claimed_at = NULL, lease_expires_at = NULL
            WHERE tenant_id = ? AND job_id = ?
            """,
            (
                JobState.DEAD_LETTER.value if dead_letter else JobState.PENDING.value,
                iso_datetime(max(moment, from_iso_datetime(row["updated_at"]) or moment)),
                "expired_claim_ambiguous_delivery" if ambiguous else "expired_claim_attempts_exhausted_ambiguous_delivery" if exhausted else row["last_error"],
                tenant_id,
                str(row["job_id"]),
            ),
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
