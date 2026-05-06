from __future__ import annotations

from contextlib import contextmanager
import importlib
from pathlib import Path

from runtime.platform.outbox.sqlite_pragmas import configure_sqlite, is_prod_env
from runtime.queue._sqlite_job_store_codec import row_to_job, write_full_row
from dataclasses import replace

from runtime.queue.job_contract import JobRecord, JobState, normalize_now
from runtime.queue.job_fencing import validate_fencing_token

sqlite3 = importlib.import_module("sqlite3")

CANON_RUNTIME_QUEUE_SQLITE_JOB_STORE_DB = True
SCHEMA_VERSION = 2
TERMINAL_REPLACEABLE_DEDUPE_STATES = {
    JobState.FAILED.value,
    JobState.DEAD_LETTER.value,
    JobState.CANCELLED.value,
}


def connect_sqlite_job_store(*, path: Path, busy_timeout_ms: int) -> sqlite3.Connection:
    db = sqlite3.connect(path, timeout=max(0.1, busy_timeout_ms / 1000.0), check_same_thread=False)
    db.row_factory = sqlite3.Row
    configure_sqlite(db, prod=is_prod_env())
    db.execute(f"PRAGMA busy_timeout={busy_timeout_ms};")
    return db


@contextmanager
def sqlite_job_store_tx(*, path: Path, busy_timeout_ms: int):
    db = connect_sqlite_job_store(path=path, busy_timeout_ms=busy_timeout_ms)
    try:
        db.execute("BEGIN IMMEDIATE;")
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_sqlite_job_store_schema(*, path: Path, busy_timeout_ms: int) -> None:
    with connect_sqlite_job_store(path=path, busy_timeout_ms=busy_timeout_ms) as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS runtime_queue_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS runtime_queue_jobs (
                tenant_id TEXT NOT NULL,
                job_id TEXT NOT NULL,
                queue_name TEXT NOT NULL,
                job_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                dedupe_key TEXT NOT NULL,
                run_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                priority INTEGER NOT NULL,
                state TEXT NOT NULL,
                attempts INTEGER NOT NULL,
                max_attempts INTEGER NOT NULL,
                last_error TEXT,
                correlation_id TEXT,
                causation_id TEXT,
                lease_owner_id TEXT,
                lease_fencing_token INTEGER NOT NULL DEFAULT 0,
                lease_claimed_at TEXT,
                lease_expires_at TEXT,
                claim_token_counter INTEGER NOT NULL DEFAULT 0,
                tags_json TEXT NOT NULL,
                PRIMARY KEY (tenant_id, job_id)
            );
            CREATE INDEX IF NOT EXISTS ix_runtime_queue_jobs_due ON runtime_queue_jobs (tenant_id, queue_name, state, run_at, priority DESC, created_at, job_id);
            CREATE INDEX IF NOT EXISTS ix_runtime_queue_jobs_claim_expiry ON runtime_queue_jobs (tenant_id, queue_name, state, lease_expires_at);
            CREATE INDEX IF NOT EXISTS ix_runtime_queue_jobs_dedupe ON runtime_queue_jobs (tenant_id, dedupe_key, created_at DESC, job_id DESC);
            """
        )
        existing = {row[1] for row in db.execute("PRAGMA table_info(runtime_queue_jobs)").fetchall()}
        if "lease_fencing_token" not in existing:
            db.execute("ALTER TABLE runtime_queue_jobs ADD COLUMN lease_fencing_token INTEGER NOT NULL DEFAULT 0")
        if "claim_token_counter" not in existing:
            db.execute("ALTER TABLE runtime_queue_jobs ADD COLUMN claim_token_counter INTEGER NOT NULL DEFAULT 0")
        db.execute(
            "INSERT INTO runtime_queue_meta (key, value) VALUES ('schema_version', ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (str(SCHEMA_VERSION),),
        )
        db.commit()


def fetch_job(db: sqlite3.Connection, *, tenant_id: str, job_id: str) -> JobRecord | None:
    row = db.execute(
        "SELECT * FROM runtime_queue_jobs WHERE tenant_id = ? AND job_id = ? LIMIT 1",
        (tenant_id, job_id),
    ).fetchone()
    return None if row is None else row_to_job(row)


def fetch_latest_by_dedupe_key(db: sqlite3.Connection, *, tenant_id: str, dedupe_key: str) -> JobRecord | None:
    rows = db.execute(
        "SELECT * FROM runtime_queue_jobs WHERE tenant_id = ? AND dedupe_key = ? ORDER BY created_at DESC, job_id DESC",
        (tenant_id, dedupe_key),
    ).fetchall()
    if not rows:
        return None
    jobs = [row_to_job(row) for row in rows]
    for item in jobs:
        if item.state.value not in TERMINAL_REPLACEABLE_DEDUPE_STATES:
            return item
    return jobs[0]


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


def require_transitionable(
    db: sqlite3.Connection,
    *,
    tenant_id: str,
    job_id: str,
    allowed_from: tuple[JobState, ...],
    owner_id: str | None = None,
    fencing_token: int | None = None,
) -> JobRecord:
    current = fetch_job(db, tenant_id=tenant_id, job_id=job_id)
    if current is None:
        raise KeyError(f"job not found: tenant_id={tenant_id} job_id={job_id}")
    if current.state not in allowed_from:
        allowed = ", ".join(item.value for item in allowed_from)
        raise ValueError(f"invalid state transition from {current.state.value}; allowed from: {allowed}")
    if current.state is JobState.CLAIMED:
        validate_claim_guard(current, owner_id, fencing_token)
    return current


def transition_terminal(
    db: sqlite3.Connection,
    *,
    tenant_id: str,
    job_id: str,
    allowed_from: tuple[JobState, ...],
    next_state: JobState,
    error: str | None,
    owner_id: str | None,
    fencing_token: int | None,
    now,
) -> JobRecord:
    current = require_transitionable(
        db,
        tenant_id=tenant_id,
        job_id=job_id,
        allowed_from=allowed_from,
        owner_id=owner_id,
        fencing_token=fencing_token,
    )
    updated = replace(current, state=next_state, lease=None, last_error=error, updated_at=max(normalize_now(now), current.updated_at))
    write_full_row(db, updated)
    saved = fetch_job(db, tenant_id=tenant_id, job_id=job_id)
    assert saved is not None
    return saved


__all__ = [
    "CANON_RUNTIME_QUEUE_SQLITE_JOB_STORE_DB",
    "SCHEMA_VERSION",
    "TERMINAL_REPLACEABLE_DEDUPE_STATES",
    "connect_sqlite_job_store",
    "fetch_job",
    "fetch_latest_by_dedupe_key",
    "init_sqlite_job_store_schema",
    "require_transitionable",
    "sqlite_job_store_tx",
    "transition_terminal",
    "validate_claim_guard",
]
