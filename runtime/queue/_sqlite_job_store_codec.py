from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from runtime.queue.job_contract import JobLease, JobRecord, JobState, normalize_now

CANON_RUNTIME_QUEUE_SQLITE_JOB_STORE_CODEC = True


def iso_datetime(value: datetime) -> str:
    return normalize_now(value).isoformat()


def from_iso_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return normalize_now(datetime.fromisoformat(text))


def payload_json(job: JobRecord) -> str:
    return job.serialized_payload()


def payload_hash(payload_json_text: str) -> str:
    return hashlib.sha256(payload_json_text.encode("utf-8")).hexdigest()


def serialize_tags(tags: tuple[str, ...]) -> str:
    return json.dumps(list(tags), ensure_ascii=False, separators=(",", ":"))


def deserialize_tags(raw: str | None) -> tuple[str, ...]:
    if raw is None:
        return ()
    text = str(raw).strip()
    if not text:
        return ()
    value = json.loads(text)
    if not isinstance(value, list):
        raise ValueError("tags_json must decode to a list")
    return tuple(str(item).strip() for item in value if str(item).strip())


def row_to_job(row: Any) -> JobRecord:
    lease: JobLease | None = None
    if row["lease_owner_id"] and row["lease_claimed_at"] and row["lease_expires_at"]:
        lease = JobLease(
            owner_id=str(row["lease_owner_id"]),
            fencing_token=int(row["lease_fencing_token"] or 0),
            claimed_at=from_iso_datetime(str(row["lease_claimed_at"])) or normalize_now(),
            expires_at=from_iso_datetime(str(row["lease_expires_at"])) or normalize_now(),
        )
    return JobRecord(
        tenant_id=str(row["tenant_id"]),
        job_id=str(row["job_id"]),
        queue_name=str(row["queue_name"]),
        job_type=str(row["job_type"]),
        payload=json.loads(str(row["payload_json"])),
        dedupe_key=str(row["dedupe_key"]),
        run_at=from_iso_datetime(str(row["run_at"])) or normalize_now(),
        created_at=from_iso_datetime(str(row["created_at"])) or normalize_now(),
        updated_at=from_iso_datetime(str(row["updated_at"])) or normalize_now(),
        priority=int(row["priority"]),
        state=JobState(str(row["state"])),
        attempts=int(row["attempts"]),
        max_attempts=int(row["max_attempts"]),
        last_error=None if row["last_error"] is None else str(row["last_error"]),
        correlation_id=None if row["correlation_id"] is None else str(row["correlation_id"]),
        causation_id=None if row["causation_id"] is None else str(row["causation_id"]),
        lease=lease,
        tags=deserialize_tags(row["tags_json"]),
    )


def write_full_row(db: Any, job: JobRecord) -> None:
    job.validate()
    encoded_payload = payload_json(job)
    db.execute(
        """
        UPDATE runtime_queue_jobs
        SET queue_name = ?, job_type = ?, payload_json = ?, payload_hash = ?, dedupe_key = ?, run_at = ?, created_at = ?, updated_at = ?, priority = ?, state = ?, attempts = ?, max_attempts = ?, last_error = ?, correlation_id = ?, causation_id = ?, lease_owner_id = ?, lease_fencing_token = ?, lease_claimed_at = ?, lease_expires_at = ?, tags_json = ?
        WHERE tenant_id = ? AND job_id = ?
        """,
        (
            job.queue_name,
            job.job_type,
            encoded_payload,
            payload_hash(encoded_payload),
            job.dedupe_key,
            iso_datetime(job.run_at),
            iso_datetime(job.created_at),
            iso_datetime(job.updated_at),
            int(job.priority),
            job.state.value,
            int(job.attempts),
            int(job.max_attempts),
            job.last_error,
            job.correlation_id,
            job.causation_id,
            job.lease.owner_id if job.lease else None,
            int(job.lease.fencing_token) if job.lease else 0,
            iso_datetime(job.lease.claimed_at) if job.lease else None,
            iso_datetime(job.lease.expires_at) if job.lease else None,
            serialize_tags(job.tags),
            job.tenant_id,
            job.job_id,
        ),
    )


__all__ = [
    "CANON_RUNTIME_QUEUE_SQLITE_JOB_STORE_CODEC",
    "deserialize_tags",
    "from_iso_datetime",
    "iso_datetime",
    "payload_hash",
    "payload_json",
    "row_to_job",
    "serialize_tags",
    "write_full_row",
]
