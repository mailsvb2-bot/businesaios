from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import sqlite3
from threading import RLock
from typing import Any, Iterator, Mapping


CANON_MARKET_INTELLIGENCE_STATE_STORE = True


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _safe_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


@dataclass(frozen=True)
class SyncCheckpoint:
    tenant_id: str
    provider: str
    source_family: str
    scope_key: str
    cursor: str | None
    last_seen_at: str | None
    checksum: str | None
    schema_version: int = 1
    metadata: Mapping[str, Any] | None = None


class SqliteMarketIntelligenceStateStore:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or Path('.runtime_data/market_intelligence/state.sqlite3')
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._migrate()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=FULL')
            conn.execute('PRAGMA foreign_keys=ON')
            conn.execute('PRAGMA busy_timeout=5000')
            try:
                yield conn
            finally:
                conn.close()

    def _migrate(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS mi_schema_version (
                    version INTEGER NOT NULL PRIMARY KEY,
                    applied_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS mi_checkpoint (
                    tenant_id TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    source_family TEXT NOT NULL,
                    scope_key TEXT NOT NULL,
                    cursor TEXT,
                    last_seen_at TEXT,
                    checksum TEXT,
                    schema_version INTEGER NOT NULL,
                    metadata_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, provider, source_family, scope_key)
                );

                CREATE TABLE IF NOT EXISTS mi_run_journal (
                    run_id TEXT NOT NULL PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    source_family TEXT NOT NULL,
                    scope_key TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    checkpoint_before_json TEXT NOT NULL,
                    checkpoint_after_json TEXT NOT NULL,
                    error_code TEXT,
                    error_message TEXT,
                    records_count INTEGER NOT NULL DEFAULT 0,
                    pages_fetched INTEGER NOT NULL DEFAULT 0,
                    poisoned INTEGER NOT NULL DEFAULT 0,
                    quarantined INTEGER NOT NULL DEFAULT 0,
                    replay_key TEXT,
                    metadata_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS mi_dead_letter (
                    event_id TEXT NOT NULL PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    source_family TEXT NOT NULL,
                    scope_key TEXT NOT NULL,
                    reason_code TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS mi_quarantine (
                    tenant_id TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    source_family TEXT NOT NULL,
                    scope_key TEXT NOT NULL,
                    reason_code TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    quarantined_at TEXT NOT NULL,
                    released_at TEXT,
                    PRIMARY KEY (tenant_id, provider, source_family, scope_key)
                );

                CREATE UNIQUE INDEX IF NOT EXISTS idx_mi_replay_key ON mi_run_journal (tenant_id, provider, source_family, scope_key, replay_key);
                CREATE INDEX IF NOT EXISTS idx_mi_run_journal_scope ON mi_run_journal (tenant_id, provider, source_family, scope_key, started_at);
                CREATE INDEX IF NOT EXISTS idx_mi_dead_letter_scope ON mi_dead_letter (tenant_id, provider, source_family, scope_key, created_at);
                CREATE INDEX IF NOT EXISTS idx_mi_quarantine_scope ON mi_quarantine (tenant_id, provider, source_family, scope_key, quarantined_at);
                """
            )
            if conn.execute('SELECT COUNT(*) FROM mi_schema_version').fetchone()[0] == 0:
                conn.execute('INSERT INTO mi_schema_version(version, applied_at) VALUES(?, ?)', (1, _utc_now()))
            conn.commit()

    def load_checkpoint(self, *, tenant_id: str, provider: str, source_family: str, scope_key: str) -> SyncCheckpoint:
        with self._connect() as conn:
            row = conn.execute(
                'SELECT tenant_id, provider, source_family, scope_key, cursor, last_seen_at, checksum, schema_version, metadata_json FROM mi_checkpoint WHERE tenant_id=? AND provider=? AND source_family=? AND scope_key=?',
                (tenant_id, provider, source_family, scope_key),
            ).fetchone()
        if row is None:
            return SyncCheckpoint(tenant_id, provider, source_family, scope_key, None, None, None, 1, {})
        return SyncCheckpoint(
            tenant_id=row['tenant_id'],
            provider=row['provider'],
            source_family=row['source_family'],
            scope_key=row['scope_key'],
            cursor=row['cursor'],
            last_seen_at=row['last_seen_at'],
            checksum=row['checksum'],
            schema_version=int(row['schema_version']),
            metadata=json.loads(row['metadata_json'] or '{}'),
        )

    def save_checkpoint(self, checkpoint: SyncCheckpoint) -> SyncCheckpoint:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO mi_checkpoint(tenant_id, provider, source_family, scope_key, cursor, last_seen_at, checksum, schema_version, metadata_json, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, provider, source_family, scope_key)
                DO UPDATE SET cursor=excluded.cursor, last_seen_at=excluded.last_seen_at, checksum=excluded.checksum, schema_version=excluded.schema_version, metadata_json=excluded.metadata_json, updated_at=excluded.updated_at
                """,
                (
                    checkpoint.tenant_id,
                    checkpoint.provider,
                    checkpoint.source_family,
                    checkpoint.scope_key,
                    checkpoint.cursor,
                    checkpoint.last_seen_at,
                    checkpoint.checksum,
                    checkpoint.schema_version,
                    _safe_json(dict(checkpoint.metadata or {})),
                    _utc_now(),
                ),
            )
            conn.commit()
        return checkpoint

    def begin_run(self, *, run_id: str, tenant_id: str, provider: str, source_family: str, scope_key: str, operation: str, replay_key: str | None, checkpoint_before: SyncCheckpoint, metadata: Mapping[str, Any] | None = None) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO mi_run_journal(run_id, tenant_id, provider, source_family, scope_key, operation, status, started_at, checkpoint_before_json, checkpoint_after_json, replay_key, metadata_json)
                VALUES(?, ?, ?, ?, ?, ?, 'running', ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    tenant_id,
                    provider,
                    source_family,
                    scope_key,
                    operation,
                    _utc_now(),
                    _safe_json(checkpoint_before.__dict__),
                    _safe_json({}),
                    replay_key,
                    _safe_json(dict(metadata or {})),
                ),
            )
            conn.commit()

    def finish_run(self, *, run_id: str, status: str, checkpoint_after: SyncCheckpoint, records_count: int, pages_fetched: int, error_code: str | None = None, error_message: str | None = None, poisoned: bool = False, quarantined: bool = False) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE mi_run_journal
                SET status=?, finished_at=?, checkpoint_after_json=?, records_count=?, pages_fetched=?, error_code=?, error_message=?, poisoned=?, quarantined=?
                WHERE run_id=?
                """,
                (status, _utc_now(), _safe_json(checkpoint_after.__dict__), int(records_count), int(pages_fetched), error_code, error_message, 1 if poisoned else 0, 1 if quarantined else 0, run_id),
            )
            conn.commit()

    def has_successful_replay(self, *, tenant_id: str, provider: str, source_family: str, scope_key: str, replay_key: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM mi_run_journal WHERE tenant_id=? AND provider=? AND source_family=? AND scope_key=? AND replay_key=? AND status='succeeded' LIMIT 1",
                (tenant_id, provider, source_family, scope_key, replay_key),
            ).fetchone()
        return row is not None

    def reconcile_incomplete_runs(self, *, tenant_id: str | None = None) -> tuple[dict[str, Any], ...]:
        sql = "SELECT * FROM mi_run_journal WHERE status='running'"
        args: list[Any] = []
        if tenant_id:
            sql += ' AND tenant_id=?'
            args.append(tenant_id)
        sql += ' ORDER BY started_at ASC'
        with self._connect() as conn:
            rows = conn.execute(sql, args).fetchall()
        return tuple(dict(row) for row in rows)

    def quarantine_scope(self, *, tenant_id: str, provider: str, source_family: str, scope_key: str, reason_code: str, details: Mapping[str, Any] | None = None) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO mi_quarantine(tenant_id, provider, source_family, scope_key, reason_code, details_json, quarantined_at, released_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, NULL)
                ON CONFLICT(tenant_id, provider, source_family, scope_key)
                DO UPDATE SET reason_code=excluded.reason_code, details_json=excluded.details_json, quarantined_at=excluded.quarantined_at, released_at=NULL
                """,
                (tenant_id, provider, source_family, scope_key, reason_code, _safe_json(dict(details or {})), _utc_now()),
            )
            conn.commit()

    def release_quarantine(self, *, tenant_id: str, provider: str, source_family: str, scope_key: str) -> None:
        with self._connect() as conn:
            conn.execute(
                'UPDATE mi_quarantine SET released_at=? WHERE tenant_id=? AND provider=? AND source_family=? AND scope_key=? AND released_at IS NULL',
                (_utc_now(), tenant_id, provider, source_family, scope_key),
            )
            conn.commit()

    def is_quarantined(self, *, tenant_id: str, provider: str, source_family: str, scope_key: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                'SELECT 1 FROM mi_quarantine WHERE tenant_id=? AND provider=? AND source_family=? AND scope_key=? AND released_at IS NULL',
                (tenant_id, provider, source_family, scope_key),
            ).fetchone()
        return row is not None

    def dead_letter(self, *, event_id: str, run_id: str, tenant_id: str, provider: str, source_family: str, scope_key: str, reason_code: str, payload: Mapping[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                'INSERT OR REPLACE INTO mi_dead_letter(event_id, run_id, tenant_id, provider, source_family, scope_key, reason_code, payload_json, created_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (event_id, run_id, tenant_id, provider, source_family, scope_key, reason_code, _safe_json(dict(payload)), _utc_now()),
            )
            conn.commit()

    def retention_compact(self, *, keep_days: int = 30) -> dict[str, int]:
        cutoff = (datetime.now(UTC) - timedelta(days=max(1, int(keep_days)))).isoformat()
        with self._connect() as conn:
            deleted_runs = conn.execute('DELETE FROM mi_run_journal WHERE finished_at IS NOT NULL AND finished_at < ?', (cutoff,)).rowcount
            deleted_dlq = conn.execute('DELETE FROM mi_dead_letter WHERE created_at < ?', (cutoff,)).rowcount
            conn.commit()
        return {'deleted_runs': int(deleted_runs), 'deleted_dead_letters': int(deleted_dlq)}
