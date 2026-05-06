from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

from core.tenancy.normalization import require_tenant_id
from runtime.queue.job_contract import JobLease, JobRecord, JobState, normalize_now
from runtime.queue.job_fencing import validate_fencing_token

CANON_RUNTIME_QUEUE_INMEMORY_JOB_STORE_OPS = True

TERMINAL_REPLACEABLE_DEDUPE_STATES = {
    JobState.FAILED,
    JobState.DEAD_LETTER,
    JobState.CANCELLED,
}

JobMap = dict[tuple[str, str], JobRecord]
DedupeMap = dict[tuple[str, str], str]
ClaimTokenMap = dict[tuple[str, str], int]

def validate_claim_guard(current: JobRecord, owner_id: str | None, fencing_token: int | None) -> None:
    if owner_id is None and fencing_token is None:
        return
    if current.state is not JobState.CLAIMED or current.lease is None:
        raise ValueError("claim-scoped transition requires claimed job")
    if owner_id is not None and current.lease.owner_id != str(owner_id).strip():
        raise ValueError("claim-scoped transition rejected: lease owner mismatch")
    token = validate_fencing_token(fencing_token=fencing_token)
    if token is not None and current.lease.fencing_token != token:
        raise ValueError("claim-scoped transition rejected: fencing token mismatch")

def put_job(*, jobs: JobMap, by_dedupe: DedupeMap, claim_tokens: ClaimTokenMap, job: JobRecord) -> JobRecord:
    job.validate()
    key = (require_tenant_id(job.tenant_id), str(job.job_id))
    dedupe_key = (job.tenant_id, str(job.dedupe_key))
    existing = jobs.get(key)
    if existing is not None:
        if (
            existing.serialized_payload() != job.serialized_payload()
            or existing.job_type != job.job_type
            or existing.queue_name != job.queue_name
            or existing.dedupe_key != job.dedupe_key
        ):
            raise ValueError(f"job_id already exists with different content: {job.job_id}")
        return existing
    existing_job_id = by_dedupe.get(dedupe_key)
    if existing_job_id is not None:
        existing_dedupe_job = jobs[(job.tenant_id, existing_job_id)]
        if existing_dedupe_job.state in TERMINAL_REPLACEABLE_DEDUPE_STATES:
            by_dedupe[dedupe_key] = job.job_id
        else:
            return existing_dedupe_job
    jobs[key] = job
    by_dedupe[dedupe_key] = job.job_id
    claim_tokens.setdefault(key, 0)
    return job

def get_job(*, jobs: JobMap, tenant_id: str, job_id: str) -> JobRecord | None:
    return jobs.get((require_tenant_id(tenant_id), str(job_id).strip()))

def get_job_by_dedupe_key(*, jobs: JobMap, by_dedupe: DedupeMap, tenant_id: str, dedupe_key: str) -> JobRecord | None:
    tid = require_tenant_id(tenant_id)
    dkey = str(dedupe_key).strip()
    if not dkey:
        raise ValueError("dedupe_key is required")
    existing_id = by_dedupe.get((tid, dkey))
    if existing_id is None:
        return None
    return jobs.get((tid, existing_id))

def count_queue_jobs(*, jobs: JobMap, tenant_id: str, queue_name: str, state: JobState | None = None) -> int:
    tid = require_tenant_id(tenant_id)
    qn = str(queue_name).strip()
    if not qn:
        raise ValueError("queue_name is required")
    return sum(
        1
        for (job_tenant_id, _), job in jobs.items()
        if job_tenant_id == tid and job.queue_name == qn and (state is None or job.state is state)
    )

def list_due_jobs(*, jobs: JobMap, tenant_id: str, queue_name: str, limit: int = 100, now: datetime | None = None) -> tuple[JobRecord, ...]:
    tid = require_tenant_id(tenant_id)
    qn = str(queue_name).strip()
    if not qn:
        raise ValueError("queue_name is required")
    moment = normalize_now(now)
    items = [
        job
        for (job_tenant_id, _), job in jobs.items()
        if job_tenant_id == tid and job.queue_name == qn and job.is_claimable(now=moment)
    ]
    items.sort(key=lambda item: (-int(item.priority), item.run_at, item.created_at, item.job_id))
    return tuple(items[: max(0, int(limit))])

def claim_job(*, jobs: JobMap, claim_tokens: ClaimTokenMap, tenant_id: str, job_id: str, owner_id: str, lease_seconds: int = 60, now: datetime | None = None) -> JobRecord | None:
    tid = require_tenant_id(tenant_id)
    key = (tid, str(job_id).strip())
    moment = normalize_now(now)
    owner = str(owner_id).strip()
    if not owner:
        raise ValueError("owner_id is required")
    current = jobs.get(key)
    if current is None or not current.is_claimable(now=moment):
        return None
    token = int(claim_tokens.get(key, 0)) + 1
    claim_tokens[key] = token
    updated = replace(
        current,
        state=JobState.CLAIMED,
        lease=JobLease(
            owner_id=owner,
            fencing_token=token,
            claimed_at=moment,
            expires_at=moment + timedelta(seconds=max(1, int(lease_seconds))),
        ),
        updated_at=max(moment, current.updated_at),
        attempts=int(current.attempts) + 1,
    )
    jobs[key] = updated
    return updated

def get_active_claim(*, jobs: JobMap, tenant_id: str, job_id: str, owner_id: str | None = None, fencing_token: int | None = None, now: datetime | None = None) -> JobRecord | None:
    current = get_job(jobs=jobs, tenant_id=tenant_id, job_id=job_id)
    if current is None or current.state is not JobState.CLAIMED or current.lease is None:
        return None
    if not current.lease.is_live(now=now):
        return None
    if owner_id is not None and current.lease.owner_id != str(owner_id).strip():
        return None
    token = validate_fencing_token(fencing_token=fencing_token)
    if token is not None and current.lease.fencing_token != token:
        return None
    return current

def renew_claim_lease(*, jobs: JobMap, tenant_id: str, job_id: str, owner_id: str, lease_seconds: int = 60, fencing_token: int | None = None, now: datetime | None = None) -> JobRecord | None:
    moment = normalize_now(now)
    owner = str(owner_id).strip()
    if not owner:
        raise ValueError("owner_id is required")
    token = validate_fencing_token(fencing_token=fencing_token)
    current = jobs.get((require_tenant_id(tenant_id), str(job_id).strip()))
    if current is None:
        raise KeyError(f"job not found: tenant_id={tenant_id} job_id={job_id}")
    if current.state is not JobState.CLAIMED or current.lease is None or current.lease.owner_id != owner:
        return None
    if token is not None and current.lease.fencing_token != token:
        return None
    renew_from = max(moment, current.lease.expires_at)
    updated = replace(
        current,
        lease=JobLease(
            owner_id=owner,
            fencing_token=current.lease.fencing_token,
            claimed_at=current.lease.claimed_at,
            expires_at=renew_from + timedelta(seconds=max(1, int(lease_seconds))),
        ),
        updated_at=max(moment, current.updated_at),
    )
    jobs[(updated.tenant_id, updated.job_id)] = updated
    return updated

def release_claim(*, jobs: JobMap, tenant_id: str, job_id: str, owner_id: str, fencing_token: int | None = None, now: datetime | None = None) -> JobRecord | None:
    owner = str(owner_id).strip()
    if not owner:
        raise ValueError("owner_id is required")
    token = validate_fencing_token(fencing_token=fencing_token)
    moment = normalize_now(now)
    current = jobs.get((require_tenant_id(tenant_id), str(job_id).strip()))
    if current is None:
        raise KeyError(f"job not found: tenant_id={tenant_id} job_id={job_id}")
    if current.state is not JobState.CLAIMED or current.lease is None or current.lease.owner_id != owner:
        return None
    if token is not None and current.lease.fencing_token != token:
        return None
    updated = replace(current, state=JobState.PENDING, lease=None, updated_at=max(moment, current.updated_at))
    jobs[(updated.tenant_id, updated.job_id)] = updated
    return updated

def reap_expired_claim_jobs(*, jobs: JobMap, tenant_id: str, queue_name: str, now: datetime | None = None) -> int:
    tid = require_tenant_id(tenant_id)
    qn = str(queue_name).strip()
    if not qn:
        raise ValueError("queue_name is required")
    moment = normalize_now(now)
    changed = 0
    for key, current in list(jobs.items()):
        if key[0] != tid or current.queue_name != qn:
            continue
        if current.state is not JobState.CLAIMED or current.lease is None or not current.lease.is_expired(now=moment):
            continue
        jobs[key] = replace(current, state=JobState.PENDING, lease=None, updated_at=max(moment, current.updated_at))
        changed += 1
    return changed

def require_job(*, jobs: JobMap, tenant_id: str, job_id: str) -> JobRecord:
    current = get_job(jobs=jobs, tenant_id=tenant_id, job_id=job_id)
    if current is None:
        raise KeyError(f"job not found: tenant_id={tenant_id} job_id={job_id}")
    return current

def require_transitionable(*, jobs: JobMap, tenant_id: str, job_id: str, allowed_from: tuple[JobState, ...]) -> JobRecord:
    current = require_job(jobs=jobs, tenant_id=tenant_id, job_id=job_id)
    if current.state not in allowed_from:
        allowed = ", ".join(item.value for item in allowed_from)
        raise ValueError(f"invalid state transition from {current.state.value}; allowed from: {allowed}")
    return current

def mark_succeeded(*, jobs: JobMap, tenant_id: str, job_id: str, owner_id: str | None = None, fencing_token: int | None = None, now: datetime | None = None) -> JobRecord:
    current = require_transitionable(jobs=jobs, tenant_id=tenant_id, job_id=job_id, allowed_from=(JobState.CLAIMED,))
    validate_claim_guard(current, owner_id, fencing_token)
    moment = normalize_now(now)
    updated = replace(current, state=JobState.SUCCEEDED, lease=None, updated_at=max(moment, current.updated_at), last_error=None)
    jobs[(updated.tenant_id, updated.job_id)] = updated
    return updated

def reschedule_job(*, jobs: JobMap, tenant_id: str, job_id: str, delay_seconds: int, error: str, owner_id: str | None = None, fencing_token: int | None = None, now: datetime | None = None) -> JobRecord:
    current = require_transitionable(jobs=jobs, tenant_id=tenant_id, job_id=job_id, allowed_from=(JobState.CLAIMED,))
    validate_claim_guard(current, owner_id, fencing_token)
    moment = normalize_now(now)
    updated = replace(
        current,
        state=JobState.PENDING,
        lease=None,
        last_error=str(error),
        run_at=moment + timedelta(seconds=max(0, int(delay_seconds))),
        updated_at=max(moment, current.updated_at),
    )
    jobs[(updated.tenant_id, updated.job_id)] = updated
    return updated

def mark_failed(*, jobs: JobMap, tenant_id: str, job_id: str, error: str, owner_id: str | None = None, fencing_token: int | None = None, now: datetime | None = None) -> JobRecord:
    current = require_transitionable(jobs=jobs, tenant_id=tenant_id, job_id=job_id, allowed_from=(JobState.CLAIMED,))
    validate_claim_guard(current, owner_id, fencing_token)
    moment = normalize_now(now)
    updated = replace(current, state=JobState.FAILED, lease=None, updated_at=max(moment, current.updated_at), last_error=str(error))
    jobs[(updated.tenant_id, updated.job_id)] = updated
    return updated

def mark_dead_letter(*, jobs: JobMap, tenant_id: str, job_id: str, error: str, owner_id: str | None = None, fencing_token: int | None = None, now: datetime | None = None) -> JobRecord:
    current = require_transitionable(
        jobs=jobs,
        tenant_id=tenant_id,
        job_id=job_id,
        allowed_from=(JobState.PENDING, JobState.CLAIMED, JobState.FAILED),
    )
    if current.state is JobState.CLAIMED:
        validate_claim_guard(current, owner_id, fencing_token)
    moment = normalize_now(now)
    updated = replace(current, state=JobState.DEAD_LETTER, lease=None, updated_at=max(moment, current.updated_at), last_error=str(error))
    jobs[(updated.tenant_id, updated.job_id)] = updated
    return updated

def purge_terminal_job_records(*, jobs: JobMap, by_dedupe: DedupeMap, claim_tokens: ClaimTokenMap, tenant_id: str, queue_name: str, states: tuple[JobState, ...], older_than: datetime, limit: int = 1000) -> int:
    tid = require_tenant_id(tenant_id)
    qn = str(queue_name).strip()
    if not qn:
        raise ValueError("queue_name is required")
    cutoff = normalize_now(older_than)
    allowed_states = tuple(item for item in states if item.is_terminal)
    if not allowed_states:
        return 0
    budget = max(0, int(limit))
    if budget == 0:
        return 0
    keys = [
        key
        for key, job in jobs.items()
        if key[0] == tid and job.queue_name == qn and job.state in allowed_states and job.updated_at <= cutoff
    ]
    keys.sort(key=lambda item: (jobs[item].updated_at, jobs[item].job_id))
    removed = 0
    for key in keys[:budget]:
        job = jobs.pop(key)
        by_dedupe.pop((job.tenant_id, job.dedupe_key), None)
        claim_tokens.pop(key, None)
        removed += 1
    return removed

__all__ = [
    "CANON_RUNTIME_QUEUE_INMEMORY_JOB_STORE_OPS",
    "ClaimTokenMap",
    "DedupeMap",
    "JobMap",
    "TERMINAL_REPLACEABLE_DEDUPE_STATES",
    "claim_job",
    "count_queue_jobs",
    "get_active_claim",
    "get_job",
    "get_job_by_dedupe_key",
    "list_due_jobs",
    "mark_dead_letter",
    "mark_failed",
    "mark_succeeded",
    "put_job",
    "purge_terminal_job_records",
    "reap_expired_claim_jobs",
    "release_claim",
    "renew_claim_lease",
    "require_job",
    "require_transitionable",
    "reschedule_job",
    "validate_claim_guard",
]
