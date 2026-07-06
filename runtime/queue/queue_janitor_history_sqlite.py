"""Durable history store for queue janitor and leadership events.

This module persists operational telemetry only. It must never mutate queue
execution state or become another decision surface.
"""

from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import RLock

from runtime.platform.outbox.sqlite_pragmas import configure_sqlite, is_prod_env
from runtime.queue.job_contract import normalize_now
from runtime.queue.queue_operational_contracts import QueueJanitorReport, QueueLeadershipReport

sqlite3 = importlib.import_module("sqlite3")
CANON_RUNTIME_QUEUE_JANITOR_HISTORY_SQLITE = True

def runtime_queue_janitor_history_store_path() -> Path:
    explicit = os.getenv('BUSINESAIOS_QUEUE_JANITOR_HISTORY_SQLITE_PATH', '').strip()
    if explicit:
        return Path(explicit)
    data_dir = os.getenv('DATA_DIR', 'data').strip() or 'data'
    return Path(data_dir) / 'runtime' / 'queue_janitor_history.sqlite3'


@dataclass(frozen=True)
class QueueJanitorHistoryEntry:
    tenant_id: str
    queue_name: str
    reclaimed_expired_claims: int
    pending_jobs: int
    active_claims: int
    is_leader: bool
    reason: str
    ran_at: datetime


@dataclass(frozen=True)
class QueueLeadershipHistoryEntry:
    tenant_id: str
    queue_name: str
    role: str
    owner_id: str
    is_leader: bool
    fencing_token: int | None
    seen_at: datetime


class SqliteQueueJanitorHistoryStore:
    def __init__(self, path: str | Path | None = None, *, busy_timeout_ms: int = 5000) -> None:
        self._path = Path(path) if path is not None else runtime_queue_janitor_history_store_path()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._busy_timeout_ms = max(100, int(busy_timeout_ms))
        self._lock = RLock()
        self._closed = False
        self._init_schema()

    def close(self) -> None:
        with self._lock:
            self._closed = True

    def record_janitor_tick(self, report: QueueJanitorReport) -> None:
        self._ensure_open()
        moment = normalize_now(report.ran_at)
        with self._lock, self._connect() as db:
            db.execute('BEGIN IMMEDIATE;')
            db.execute(
                """
                INSERT INTO runtime_queue_janitor_history (
                    tenant_id,
                    queue_name,
                    reclaimed_expired_claims,
                    pending_jobs,
                    active_claims,
                    is_leader,
                    reason,
                    ran_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(report.tenant_id).strip(),
                    str(report.queue_name).strip(),
                    int(report.reclaimed_expired_claims),
                    int(report.pending_jobs),
                    int(report.active_claims),
                    1 if report.is_leader else 0,
                    str(report.reason),
                    moment.isoformat(),
                ),
            )
            db.commit()

    def record_leadership(self, report: QueueLeadershipReport, *, seen_at: datetime | None = None) -> None:
        self._ensure_open()
        moment = normalize_now(seen_at)
        with self._lock, self._connect() as db:
            db.execute('BEGIN IMMEDIATE;')
            db.execute(
                """
                INSERT INTO runtime_queue_leadership_history (
                    tenant_id,
                    queue_name,
                    role,
                    owner_id,
                    is_leader,
                    fencing_token,
                    seen_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(report.tenant_id).strip(),
                    str(report.queue_name).strip(),
                    str(report.role).strip(),
                    str(report.owner_id).strip(),
                    1 if report.is_leader else 0,
                    report.fencing_token,
                    moment.isoformat(),
                ),
            )
            db.commit()

    def snapshot_janitor_runs(self, *, tenant_id: str | None = None, queue_name: str | None = None, limit: int = 1000) -> tuple[QueueJanitorHistoryEntry, ...]:
        self._ensure_open()
        sql = (
            'SELECT tenant_id, queue_name, reclaimed_expired_claims, pending_jobs, active_claims, '
            'is_leader, reason, ran_at FROM runtime_queue_janitor_history'
        )
        args: list[object] = []
        filters: list[str] = []
        if tenant_id is not None:
            filters.append('tenant_id = ?')
            args.append(str(tenant_id).strip())
        if queue_name is not None:
            filters.append('queue_name = ?')
            args.append(str(queue_name).strip())
        if filters:
            sql += ' WHERE ' + ' AND '.join(filters)
        sql += ' ORDER BY id ASC LIMIT ?'
        args.append(max(0, int(limit)))
        with self._lock, self._connect() as db:
            rows = db.execute(sql, tuple(args)).fetchall()
        return tuple(
            QueueJanitorHistoryEntry(
                tenant_id=str(row['tenant_id']),
                queue_name=str(row['queue_name']),
                reclaimed_expired_claims=int(row['reclaimed_expired_claims']),
                pending_jobs=int(row['pending_jobs']),
                active_claims=int(row['active_claims']),
                is_leader=bool(row['is_leader']),
                reason=str(row['reason']),
                ran_at=normalize_now(datetime.fromisoformat(str(row['ran_at']))),
            )
            for row in rows
        )

    def snapshot_leadership_events(self, *, tenant_id: str | None = None, queue_name: str | None = None, role: str | None = None, limit: int = 1000) -> tuple[QueueLeadershipHistoryEntry, ...]:
        self._ensure_open()
        sql = (
            'SELECT tenant_id, queue_name, role, owner_id, is_leader, fencing_token, seen_at '
            'FROM runtime_queue_leadership_history'
        )
        args: list[object] = []
        filters: list[str] = []
        if tenant_id is not None:
            filters.append('tenant_id = ?')
            args.append(str(tenant_id).strip())
        if queue_name is not None:
            filters.append('queue_name = ?')
            args.append(str(queue_name).strip())
        if role is not None:
            filters.append('role = ?')
            args.append(str(role).strip())
        if filters:
            sql += ' WHERE ' + ' AND '.join(filters)
        sql += ' ORDER BY id ASC LIMIT ?'
        args.append(max(0, int(limit)))
        with self._lock, self._connect() as db:
            rows = db.execute(sql, tuple(args)).fetchall()
        return tuple(
            QueueLeadershipHistoryEntry(
                tenant_id=str(row['tenant_id']),
                queue_name=str(row['queue_name']),
                role=str(row['role']),
                owner_id=str(row['owner_id']),
                is_leader=bool(row['is_leader']),
                fencing_token=None if row['fencing_token'] is None else int(row['fencing_token']),
                seen_at=normalize_now(datetime.fromisoformat(str(row['seen_at']))),
            )
            for row in rows
        )

    def purge_older_than(self, *, older_than: datetime) -> int:
        self._ensure_open()
        cutoff = normalize_now(older_than).isoformat()
        with self._lock, self._connect() as db:
            db.execute('BEGIN IMMEDIATE;')
            janitor_removed = db.execute('DELETE FROM runtime_queue_janitor_history WHERE ran_at < ?', (cutoff,)).rowcount
            leadership_removed = db.execute('DELETE FROM runtime_queue_leadership_history WHERE seen_at < ?', (cutoff,)).rowcount
            db.commit()
        return int((janitor_removed or 0) + (leadership_removed or 0))

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self._path, timeout=max(0.1, self._busy_timeout_ms / 1000.0), check_same_thread=False)
        db.row_factory = sqlite3.Row
        configure_sqlite(db, prod=is_prod_env())
        db.execute(f'PRAGMA busy_timeout={self._busy_timeout_ms};')
        return db

    def _init_schema(self) -> None:
        with self._lock, self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS runtime_queue_janitor_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    queue_name TEXT NOT NULL,
                    reclaimed_expired_claims INTEGER NOT NULL,
                    pending_jobs INTEGER NOT NULL,
                    active_claims INTEGER NOT NULL,
                    is_leader INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    ran_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_runtime_queue_janitor_history_lookup
                    ON runtime_queue_janitor_history (tenant_id, queue_name, ran_at);

                CREATE TABLE IF NOT EXISTS runtime_queue_leadership_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    queue_name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    is_leader INTEGER NOT NULL,
                    fencing_token INTEGER,
                    seen_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_runtime_queue_leadership_history_lookup
                    ON runtime_queue_leadership_history (tenant_id, queue_name, role, seen_at);
                """
            )
            db.commit()

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError('SqliteQueueJanitorHistoryStore is closed')


__all__ = [
    'CANON_RUNTIME_QUEUE_JANITOR_HISTORY_SQLITE',
    'QueueJanitorHistoryEntry',
    'QueueLeadershipHistoryEntry',
    'SqliteQueueJanitorHistoryStore',
    'runtime_queue_janitor_history_store_path',
]
