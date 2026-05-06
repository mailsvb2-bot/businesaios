from __future__ import annotations

"""SQLite-backed durable idempotency backend."""

from contextlib import suppress
import importlib
from datetime import datetime
from pathlib import Path
from threading import RLock, local
from typing import Any, Callable, Iterable
import json
sqlite3 = importlib.import_module("sqlite3")

from reliability.idempotency_backend import (
    BackendMutationResult,
    BaseBackendIdempotencyStore,
    CANON_IDEMPOTENCY_BACKEND,
    IdempotencyBackend,
)
from reliability.idempotency_contract import IdempotencyKey, IdempotencyRecord, IdempotencyState

CANON_IDEMPOTENCY_SQLITE_BACKEND = True
_IDEMPOTENCY_SCHEMA_VERSION = 1


def _isoformat_aware(value: datetime | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f'{field_name} must be timezone-aware')
    return value.isoformat()


def _parse_datetime(value: Any, *, field_name: str) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f'{field_name} must be timezone-aware')
    return parsed


def _record_to_row(record: IdempotencyRecord) -> dict[str, Any]:
    record.validate()
    return {
        'tenant_id': record.idempotency_key.tenant_id,
        'namespace': record.idempotency_key.namespace,
        'operation': record.idempotency_key.operation,
        'idem_key': record.idempotency_key.key,
        'scope_hash': record.idempotency_key.scope_hash,
        'state': record.state.value,
        'first_seen_at': _isoformat_aware(record.first_seen_at, field_name='first_seen_at'),
        'updated_at': _isoformat_aware(record.updated_at, field_name='updated_at'),
        'lease_expires_at': _isoformat_aware(record.lease_expires_at, field_name='lease_expires_at'),
        'completed_at': _isoformat_aware(record.completed_at, field_name='completed_at'),
        'owner_id': record.owner_id,
        'attempt_count': int(record.attempt_count),
        'result_ref': record.result_ref,
        'result_digest': record.result_digest,
        'failure_reason': record.failure_reason,
        'metadata_json': json.dumps(dict(record.metadata), ensure_ascii=False, sort_keys=True, separators=(',', ':')),
    }


def _row_to_record(row: sqlite3.Row) -> IdempotencyRecord:
    key = IdempotencyKey(
        tenant_id=str(row['tenant_id']),
        namespace=str(row['namespace']),
        operation=str(row['operation']),
        key=str(row['idem_key']),
        scope_hash=str(row['scope_hash'] or ''),
    )
    record = IdempotencyRecord(
        idempotency_key=key,
        state=IdempotencyState(str(row['state'])),
        first_seen_at=_parse_datetime(row['first_seen_at'], field_name='first_seen_at'),
        updated_at=_parse_datetime(row['updated_at'], field_name='updated_at'),
        lease_expires_at=_parse_datetime(row['lease_expires_at'], field_name='lease_expires_at'),
        completed_at=_parse_datetime(row['completed_at'], field_name='completed_at'),
        owner_id=row['owner_id'],
        attempt_count=int(row['attempt_count'] or 0),
        result_ref=row['result_ref'],
        result_digest=row['result_digest'],
        failure_reason=row['failure_reason'],
        metadata=dict(json.loads(str(row['metadata_json'] or '{}'))),
    )
    record.validate()
    return record


class SQLiteIdempotencyBackend(IdempotencyBackend):
    def __init__(self, path: str | Path, *, busy_timeout_ms: int = 5000, wal_autocheckpoint_pages: int = 1000) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._busy_timeout_ms = max(1, int(busy_timeout_ms))
        self._wal_autocheckpoint_pages = max(100, int(wal_autocheckpoint_pages))
        self._local = local()
        self._init_lock = RLock()
        self._write_lock = RLock()
        self._initialized = False
        self._ensure_schema()

    @property
    def path(self) -> Path:
        return self._path

    def load(self, *, key: IdempotencyKey) -> IdempotencyRecord | None:
        key.validate()
        self._ensure_schema()
        row = self._connection().execute(
            """
            SELECT tenant_id, namespace, operation, idem_key, scope_hash, state,
                   first_seen_at, updated_at, lease_expires_at, completed_at,
                   owner_id, attempt_count, result_ref, result_digest,
                   failure_reason, metadata_json
            FROM reliability_idempotency
            WHERE tenant_id = ? AND namespace = ? AND operation = ? AND idem_key = ?
            """,
            key.as_tuple(),
        ).fetchone()
        if row is None:
            return None
        return _row_to_record(row)

    def mutate(self, *, key: IdempotencyKey, mutator: Callable[[IdempotencyRecord | None], IdempotencyRecord]) -> BackendMutationResult:
        key.validate()
        self._ensure_schema()
        with self._write_lock:
            conn = self._connection()
            conn.execute('BEGIN IMMEDIATE')
            try:
                row = conn.execute(
                    """
                    SELECT tenant_id, namespace, operation, idem_key, scope_hash, state,
                           first_seen_at, updated_at, lease_expires_at, completed_at,
                           owner_id, attempt_count, result_ref, result_digest,
                           failure_reason, metadata_json, revision
                    FROM reliability_idempotency
                    WHERE tenant_id = ? AND namespace = ? AND operation = ? AND idem_key = ?
                    """,
                    key.as_tuple(),
                ).fetchone()
                existing = None if row is None else _row_to_record(row)
                previous_revision = None if row is None else int(row['revision'])
                stored = mutator(existing)
                stored.validate()
                payload = _record_to_row(stored)
                next_revision = 1 if previous_revision is None else previous_revision + 1
                payload['revision'] = next_revision
                conn.execute(
                    """
                    INSERT INTO reliability_idempotency (
                        tenant_id, namespace, operation, idem_key, scope_hash, state,
                        first_seen_at, updated_at, lease_expires_at, completed_at,
                        owner_id, attempt_count, result_ref, result_digest,
                        failure_reason, metadata_json, revision
                    ) VALUES (
                        :tenant_id, :namespace, :operation, :idem_key, :scope_hash, :state,
                        :first_seen_at, :updated_at, :lease_expires_at, :completed_at,
                        :owner_id, :attempt_count, :result_ref, :result_digest,
                        :failure_reason, :metadata_json, :revision
                    )
                    ON CONFLICT(tenant_id, namespace, operation, idem_key)
                    DO UPDATE SET
                        scope_hash = excluded.scope_hash,
                        state = excluded.state,
                        first_seen_at = excluded.first_seen_at,
                        updated_at = excluded.updated_at,
                        lease_expires_at = excluded.lease_expires_at,
                        completed_at = excluded.completed_at,
                        owner_id = excluded.owner_id,
                        attempt_count = excluded.attempt_count,
                        result_ref = excluded.result_ref,
                        result_digest = excluded.result_digest,
                        failure_reason = excluded.failure_reason,
                        metadata_json = excluded.metadata_json,
                        revision = excluded.revision
                    """,
                    payload,
                )
                conn.execute(
                    """
                    INSERT INTO reliability_idempotency_history (
                        tenant_id, namespace, operation, idem_key, scope_hash, state,
                        first_seen_at, updated_at, lease_expires_at, completed_at,
                        owner_id, attempt_count, result_ref, result_digest,
                        failure_reason, metadata_json, revision
                    ) VALUES (
                        :tenant_id, :namespace, :operation, :idem_key, :scope_hash, :state,
                        :first_seen_at, :updated_at, :lease_expires_at, :completed_at,
                        :owner_id, :attempt_count, :result_ref, :result_digest,
                        :failure_reason, :metadata_json, :revision
                    )
                    """,
                    payload,
                )
                conn.commit()
                return BackendMutationResult(stored_record=stored, previous_record=existing, created=existing is None, revision=next_revision)
            except Exception:
                conn.rollback()
                raise

    def scan_non_terminal(self) -> Iterable[IdempotencyRecord]:
        self._ensure_schema()
        rows = self._connection().execute(
            """
            SELECT tenant_id, namespace, operation, idem_key, scope_hash, state,
                   first_seen_at, updated_at, lease_expires_at, completed_at,
                   owner_id, attempt_count, result_ref, result_digest,
                   failure_reason, metadata_json
            FROM reliability_idempotency
            WHERE state NOT IN ('completed', 'failed', 'expired')
            ORDER BY updated_at ASC, tenant_id ASC, namespace ASC, operation ASC, idem_key ASC
            """
        ).fetchall()
        for row in rows:
            yield _row_to_record(row)

    def prune_history(self, *, keep_latest_per_key: int = 32, max_rows_deleted: int = 5000) -> int:
        self._ensure_schema()
        keep_count = max(1, int(keep_latest_per_key))
        delete_limit = max(1, int(max_rows_deleted))
        with self._write_lock:
            conn = self._connection()
            conn.execute('BEGIN IMMEDIATE')
            try:
                cursor = conn.execute(
                    """
                    DELETE FROM reliability_idempotency_history
                    WHERE history_id IN (
                        SELECT history_id
                        FROM (
                            SELECT history_id,
                                   ROW_NUMBER() OVER (
                                       PARTITION BY tenant_id, namespace, operation, idem_key
                                       ORDER BY revision DESC, history_id DESC
                                   ) AS rn
                            FROM reliability_idempotency_history
                        )
                        WHERE rn > ?
                        LIMIT ?
                    )
                    """,
                    (keep_count, delete_limit),
                )
                deleted = int(cursor.rowcount or 0)
                conn.commit()
                return deleted
            except Exception:
                conn.rollback()
                raise

    def compact(self) -> None:
        conn = self._connection()
        with suppress(Exception):
            conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        with suppress(Exception):
            conn.execute('VACUUM')

    def close(self) -> None:
        conn = getattr(self._local, 'conn', None)
        if conn is not None:
            with suppress(Exception):
                conn.execute('PRAGMA wal_checkpoint(PASSIVE)')
            with suppress(Exception):
                conn.close()
            self._local.conn = None

    def _connection(self) -> sqlite3.Connection:
        conn = getattr(self._local, 'conn', None)
        if conn is None:
            conn = sqlite3.connect(str(self._path), isolation_level=None, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute(f'PRAGMA busy_timeout = {self._busy_timeout_ms}')
            conn.execute('PRAGMA journal_mode = WAL')
            conn.execute('PRAGMA synchronous = NORMAL')
            conn.execute('PRAGMA foreign_keys = ON')
            conn.execute(f'PRAGMA wal_autocheckpoint = {self._wal_autocheckpoint_pages}')
            self._local.conn = conn
        return conn

    def _ensure_schema(self) -> None:
        with self._init_lock:
            conn = self._connection()
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reliability_idempotency (
                    tenant_id TEXT NOT NULL,
                    namespace TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    idem_key TEXT NOT NULL,
                    scope_hash TEXT NOT NULL DEFAULT '',
                    state TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    lease_expires_at TEXT NULL,
                    completed_at TEXT NULL,
                    owner_id TEXT NULL,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    result_ref TEXT NULL,
                    result_digest TEXT NULL,
                    failure_reason TEXT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    revision INTEGER NOT NULL DEFAULT 1,
                    PRIMARY KEY (tenant_id, namespace, operation, idem_key)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reliability_idempotency_history (
                    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    namespace TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    idem_key TEXT NOT NULL,
                    scope_hash TEXT NOT NULL DEFAULT '',
                    state TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    lease_expires_at TEXT NULL,
                    completed_at TEXT NULL,
                    owner_id TEXT NULL,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    result_ref TEXT NULL,
                    result_digest TEXT NULL,
                    failure_reason TEXT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    revision INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reliability_idempotency_meta (
                    meta_key TEXT PRIMARY KEY,
                    meta_value TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                INSERT INTO reliability_idempotency_meta(meta_key, meta_value)
                VALUES ('schema_version', ?)
                ON CONFLICT(meta_key) DO UPDATE SET meta_value = excluded.meta_value
                """,
                (str(_IDEMPOTENCY_SCHEMA_VERSION),),
            )
            conn.execute('CREATE INDEX IF NOT EXISTS idx_reliability_idempotency_state_updated ON reliability_idempotency(state, updated_at)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_reliability_idempotency_lease_expires ON reliability_idempotency(lease_expires_at)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_reliability_idempotency_history_lookup ON reliability_idempotency_history(tenant_id, namespace, operation, idem_key, revision DESC)')
            self._initialized = True


class SQLiteIdempotencyStore(BaseBackendIdempotencyStore):
    def __init__(self, path: str | Path, *, busy_timeout_ms: int = 5000, wal_autocheckpoint_pages: int = 1000) -> None:
        backend = SQLiteIdempotencyBackend(path=path, busy_timeout_ms=busy_timeout_ms, wal_autocheckpoint_pages=wal_autocheckpoint_pages)
        self.sqlite_backend = backend
        super().__init__(backend=backend)

    @property
    def path(self) -> Path:
        return self.sqlite_backend.path

    def prune_history(self, *, keep_latest_per_key: int = 32, max_rows_deleted: int = 5000) -> int:
        return self.sqlite_backend.prune_history(keep_latest_per_key=keep_latest_per_key, max_rows_deleted=max_rows_deleted)


__all__ = [
    'CANON_IDEMPOTENCY_BACKEND',
    'CANON_IDEMPOTENCY_SQLITE_BACKEND',
    'SQLiteIdempotencyBackend',
    'SQLiteIdempotencyStore',
]