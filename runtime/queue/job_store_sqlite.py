"""SQLite-backed durable job store for runtime queue.

Infrastructure only:
- transactional queue state transitions
- durable claim / renew / release semantics
- deterministic reclaim of expired claims
- monotonic claim fencing tokens for stale-writer protection
- never a second brain
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta
from pathlib import Path
from core.tenancy.normalization import require_tenant_id
from runtime.queue import _sqlite_job_store_terminal_methods as _sqlite_job_store_terminal_methods
from runtime.queue._sqlite_job_store_claims import (
    reap_expired_claims_sqlite,
    release_claim_sqlite,
    reschedule_claimed_job_sqlite,
)
from runtime.queue._sqlite_job_store_codec import (
    iso_datetime,
    payload_hash,
    payload_json,
    row_to_job,
    serialize_tags,
    write_full_row,
)
from runtime.queue._sqlite_job_store_db import (
    TERMINAL_REPLACEABLE_DEDUPE_STATES,
    connect_sqlite_job_store,
    fetch_job,
    fetch_latest_by_dedupe_key,
    init_sqlite_job_store_schema,
    require_transitionable,
    sqlite_job_store_tx,
)
from runtime.queue._sqlite_job_store_runtime import (
    require_dedupe_key as _require_dedupe_key,
)
from runtime.queue._sqlite_job_store_runtime import (
    require_job_id as _require_job_id,
)
from runtime.queue._sqlite_job_store_runtime import (
    require_owner_id as _require_owner_id,
)
from runtime.queue._sqlite_job_store_runtime import (
    require_queue_name as _require_queue_name,
)
from runtime.queue._sqlite_job_store_runtime import (
    runtime_queue_sqlite_store_path,
)
from runtime.queue.job_contract import JobRecord, JobState, normalize_now
from runtime.queue.job_fencing import validate_fencing_token
from runtime.queue.queue_store_policy import DEFAULT_QUEUE_STORE_POLICY

CANON_RUNTIME_QUEUE_JOB_STORE_SQLITE = True

class SqliteJobStore:
    def __init__(self, path: str | Path | None = None, *, busy_timeout_ms: int = DEFAULT_QUEUE_STORE_POLICY.default_sqlite_busy_timeout_ms, wal_checkpoint_on_close: bool = DEFAULT_QUEUE_STORE_POLICY.wal_checkpoint_on_close) -> None:
        self._path = Path(path) if path is not None else runtime_queue_sqlite_store_path()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._busy_timeout_ms = DEFAULT_QUEUE_STORE_POLICY.normalize_sqlite_busy_timeout_ms(busy_timeout_ms)
        self._wal_checkpoint_on_close = bool(wal_checkpoint_on_close)
        self._lock = threading.RLock()
        self._closed = False
        self._init_schema()

    @property
    def path(self) -> Path:
        return self._path

    _require_tenant_id = staticmethod(require_tenant_id)
    _require_job_id = staticmethod(_require_job_id)
    _require_queue_name = staticmethod(_require_queue_name)
    _reschedule_claimed_job_sqlite = staticmethod(reschedule_claimed_job_sqlite)


    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            if self._wal_checkpoint_on_close:
                try:
                    with self._connect() as db:
                        db.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                except Exception:
                    pass
            self._closed = True

    def put(self, job: JobRecord) -> JobRecord:
        self._ensure_open()
        job.validate()
        encoded_payload = payload_json(job)
        payload_digest = payload_hash(encoded_payload)
        with self._lock, self._tx() as db:
            existing = self._fetch_job(db, tenant_id=job.tenant_id, job_id=job.job_id)
            if existing is not None:
                if (
                    existing.serialized_payload() != encoded_payload
                    or existing.job_type != job.job_type
                    or existing.queue_name != job.queue_name
                    or existing.dedupe_key != job.dedupe_key
                ):
                    raise ValueError(f"job_id already exists with different content: {job.job_id}")
                return existing
            dedupe_existing = self._fetch_latest_by_dedupe_key(db, tenant_id=job.tenant_id, dedupe_key=job.dedupe_key)
            if dedupe_existing is not None and dedupe_existing.state.value not in TERMINAL_REPLACEABLE_DEDUPE_STATES:
                return dedupe_existing
            db.execute(
                """
                INSERT INTO runtime_queue_jobs (
                    tenant_id, job_id, queue_name, job_type, payload_json, payload_hash,
                    dedupe_key, run_at, created_at, updated_at, priority, state,
                    attempts, max_attempts, last_error, correlation_id, causation_id,
                    lease_owner_id, lease_fencing_token, lease_claimed_at, lease_expires_at,
                    claim_token_counter, tags_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.tenant_id,
                    job.job_id,
                    job.queue_name,
                    job.job_type,
                    encoded_payload,
                    payload_digest,
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
                    int(job.lease.fencing_token) if job.lease else 0,
                    serialize_tags(job.tags),
                ),
            )
            inserted = self._fetch_job(db, tenant_id=job.tenant_id, job_id=job.job_id)
            assert inserted is not None
            return inserted

    def get(self, *, tenant_id: str, job_id: str) -> JobRecord | None:
        self._ensure_open()
        with self._lock, self._connect() as db:
            return self._fetch_job(db, tenant_id=require_tenant_id(tenant_id), job_id=_require_job_id(job_id))

    def get_by_dedupe_key(self, *, tenant_id: str, dedupe_key: str) -> JobRecord | None:
        self._ensure_open()
        with self._lock, self._connect() as db:
            return self._fetch_latest_by_dedupe_key(db, tenant_id=require_tenant_id(tenant_id), dedupe_key=_require_dedupe_key(dedupe_key))

    def count(self, *, tenant_id: str, queue_name: str, state: JobState | None = None) -> int:
        self._ensure_open()
        tid = require_tenant_id(tenant_id)
        qn = _require_queue_name(queue_name)
        args: list[object] = [tid, qn]
        sql = "SELECT COUNT(*) FROM runtime_queue_jobs WHERE tenant_id = ? AND queue_name = ?"
        if state is not None:
            sql += " AND state = ?"
            args.append(state.value)
        with self._lock, self._connect() as db:
            row = db.execute(sql, tuple(args)).fetchone()
            return int(row[0]) if row is not None else 0

    def list_due(self, *, tenant_id: str, queue_name: str, limit: int = DEFAULT_QUEUE_STORE_POLICY.default_due_limit, now: datetime | None = None) -> tuple[JobRecord, ...]:
        self._ensure_open()
        tid = require_tenant_id(tenant_id)
        qn = _require_queue_name(queue_name)
        max_items = DEFAULT_QUEUE_STORE_POLICY.normalize_due_limit(limit)
        if max_items == 0:
            return ()
        moment = normalize_now(now)
        with self._lock, self._connect() as db:
            rows = db.execute(
                """
                SELECT *
                FROM runtime_queue_jobs
                WHERE tenant_id = ? AND queue_name = ? AND state = ? AND run_at <= ?
                ORDER BY priority DESC, run_at ASC, created_at ASC, job_id ASC
                LIMIT ?
                """,
                (tid, qn, JobState.PENDING.value, iso_datetime(moment), max_items),
            ).fetchall()
            return tuple(row_to_job(row) for row in rows)

    def claim(self, *, tenant_id: str, job_id: str, owner_id: str, lease_seconds: int = DEFAULT_QUEUE_STORE_POLICY.default_claim_lease_seconds, now: datetime | None = None) -> JobRecord | None:
        self._ensure_open()
        tid = require_tenant_id(tenant_id)
        jid = _require_job_id(job_id)
        owner = _require_owner_id(owner_id)
        moment = normalize_now(now)
        expiry = moment + timedelta(seconds=DEFAULT_QUEUE_STORE_POLICY.normalize_claim_lease_seconds(lease_seconds))
        with self._lock, self._tx() as db:
            current = self._fetch_job(db, tenant_id=tid, job_id=jid)
            if current is None or not current.is_claimable(now=moment):
                return None
            row = db.execute("SELECT claim_token_counter FROM runtime_queue_jobs WHERE tenant_id = ? AND job_id = ?", (tid, jid)).fetchone()
            next_token = int(row[0]) + 1 if row is not None else 1
            db.execute(
                """
                UPDATE runtime_queue_jobs
                SET state = ?, attempts = ?, updated_at = ?, lease_owner_id = ?,
                    lease_fencing_token = ?, lease_claimed_at = ?, lease_expires_at = ?,
                    claim_token_counter = ?
                WHERE tenant_id = ? AND job_id = ?
                """,
                (
                    JobState.CLAIMED.value,
                    int(current.attempts) + 1,
                    iso_datetime(max(moment, current.updated_at)),
                    owner,
                    next_token,
                    iso_datetime(moment),
                    iso_datetime(expiry),
                    next_token,
                    tid,
                    jid,
                ),
            )
            claimed = self._fetch_job(db, tenant_id=tid, job_id=jid)
            assert claimed is not None
            return claimed

    def get_active_claim(self, *, tenant_id: str, job_id: str, owner_id: str | None = None, fencing_token: int | None = None, now: datetime | None = None) -> JobRecord | None:
        self._ensure_open()
        current = self.get(tenant_id=tenant_id, job_id=job_id)
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

    def renew_lease(self, *, tenant_id: str, job_id: str, owner_id: str, lease_seconds: int = DEFAULT_QUEUE_STORE_POLICY.default_claim_lease_seconds, fencing_token: int | None = None, now: datetime | None = None) -> JobRecord | None:
        self._ensure_open()
        tid = require_tenant_id(tenant_id)
        jid = _require_job_id(job_id)
        owner = _require_owner_id(owner_id)
        token = validate_fencing_token(fencing_token=fencing_token)
        moment = normalize_now(now)
        extension_seconds = DEFAULT_QUEUE_STORE_POLICY.normalize_claim_lease_seconds(lease_seconds)
        with self._lock, self._tx() as db:
            current = self._fetch_job(db, tenant_id=tid, job_id=jid)
            if current is None:
                raise KeyError(f"job not found: tenant_id={tenant_id} job_id={job_id}")
            if current.state is not JobState.CLAIMED or current.lease is None or current.lease.owner_id != owner:
                return None
            if token is not None and current.lease.fencing_token != token:
                return None
            renew_from = max(moment, current.lease.expires_at)
            new_expiry = renew_from + timedelta(seconds=extension_seconds)
            db.execute(
                """
                UPDATE runtime_queue_jobs
                SET updated_at = ?, lease_owner_id = ?, lease_fencing_token = ?, lease_claimed_at = ?, lease_expires_at = ?
                WHERE tenant_id = ? AND job_id = ?
                """,
                (iso_datetime(max(moment, current.updated_at)), owner, current.lease.fencing_token, iso_datetime(current.lease.claimed_at), iso_datetime(new_expiry), tid, jid),
            )
            renewed = self._fetch_job(db, tenant_id=tid, job_id=jid)
            assert renewed is not None
            return renewed

    def release_claim(self, *, tenant_id: str, job_id: str, owner_id: str, fencing_token: int | None = None, now: datetime | None = None) -> JobRecord | None:
        self._ensure_open()
        tid = require_tenant_id(tenant_id)
        jid = _require_job_id(job_id)
        owner = _require_owner_id(owner_id)
        token = validate_fencing_token(fencing_token=fencing_token)
        with self._lock, self._tx() as db:
            return release_claim_sqlite(
                db=db,
                fetch_job=self._fetch_job,
                tenant_id=tid,
                job_id=jid,
                owner_id=owner,
                fencing_token=token,
                now=now,
            )

    def reap_expired_claims(self, *, tenant_id: str, queue_name: str, now: datetime | None = None) -> int:
        self._ensure_open()
        tid = require_tenant_id(tenant_id)
        qn = _require_queue_name(queue_name)
        with self._lock, self._tx() as db:
            return reap_expired_claims_sqlite(db=db, tenant_id=tid, queue_name=qn, now=now)


    def _tx(self):
        return sqlite_job_store_tx(path=self._path, busy_timeout_ms=self._busy_timeout_ms)

    def _connect(self):
        self._ensure_open()
        return connect_sqlite_job_store(path=self._path, busy_timeout_ms=self._busy_timeout_ms)

    def _init_schema(self) -> None:
        with self._lock:
            init_sqlite_job_store_schema(path=self._path, busy_timeout_ms=self._busy_timeout_ms)

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("SqliteJobStore is closed")

    def _fetch_job(self, db, *, tenant_id: str, job_id: str) -> JobRecord | None:
        return fetch_job(db, tenant_id=tenant_id, job_id=job_id)

    def _fetch_latest_by_dedupe_key(self, db, *, tenant_id: str, dedupe_key: str) -> JobRecord | None:
        return fetch_latest_by_dedupe_key(db, tenant_id=tenant_id, dedupe_key=dedupe_key)

    def _require_transitionable(self, db, *, tenant_id: str, job_id: str, allowed_from: tuple[JobState, ...], owner_id: str | None = None, fencing_token: int | None = None) -> JobRecord:
        return require_transitionable(db, tenant_id=tenant_id, job_id=job_id, allowed_from=allowed_from, owner_id=owner_id, fencing_token=fencing_token)

    def _write_full_row(self, db, job: JobRecord) -> None:
        write_full_row(db, job)


SqliteJobStore.mark_succeeded = _sqlite_job_store_terminal_methods.mark_succeeded
SqliteJobStore.reschedule = _sqlite_job_store_terminal_methods.reschedule
SqliteJobStore.mark_failed = _sqlite_job_store_terminal_methods.mark_failed
SqliteJobStore.mark_dead_letter = _sqlite_job_store_terminal_methods.mark_dead_letter
SqliteJobStore.purge_terminal_jobs = _sqlite_job_store_terminal_methods.purge_terminal_jobs

__all__ = ["CANON_RUNTIME_QUEUE_JOB_STORE_SQLITE", "SqliteJobStore", "runtime_queue_sqlite_store_path"]
