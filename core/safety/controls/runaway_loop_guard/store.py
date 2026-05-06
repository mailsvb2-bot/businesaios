from __future__ import annotations

import sqlite3
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from sqlite3 import Connection
from threading import RLock
from typing import Iterator, Protocol

from ..support.sqlite_migrations import SafetySqliteMigrator, SchemaMigrationPlan

CANON_SAFETY_RUNAWAY_LOOP_STORE = True
SCHEMA_VERSION = 2


class RunawayLoopStore(Protocol):
    def append(self, tenant_id: str, fingerprint: str) -> tuple[str, ...]: ...


@dataclass
class InMemoryRunawayLoopStore:
    recent: dict[str, deque[str]] = field(default_factory=dict)
    maxlen: int = 5
    _lock: RLock = field(default_factory=RLock)

    def append(self, tenant_id: str, fingerprint: str) -> tuple[str, ...]:
        with self._lock:
            bucket = self.recent.setdefault(str(tenant_id), deque(maxlen=self.maxlen))
            bucket.append(str(fingerprint))
            return tuple(bucket)


class SqliteRunawayLoopStore:
    def __init__(self, *, sqlite_path: str, maxlen: int = 5) -> None:
        self._path = str(sqlite_path).strip()
        self._maxlen = max(1, int(maxlen or 1))
        if not self._path:
            raise ValueError('sqlite_path is required')
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connect(self) -> Iterator[Connection]:
        conn = sqlite3.connect(self._path)
        conn.execute('PRAGMA journal_mode = WAL')
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        plan = SchemaMigrationPlan(component='runaway_loop_history', target_version=SCHEMA_VERSION, steps=(self._migrate_v1, self._migrate_v2))
        with self._connect() as conn:
            SafetySqliteMigrator().apply(conn, plan)

    @staticmethod
    def _migrate_v1(conn: Connection) -> None:
        conn.execute(
            '''
            CREATE TABLE IF NOT EXISTS safety_runaway_loop_history (
                tenant_id TEXT NOT NULL,
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                fingerprint TEXT NOT NULL
            )
            '''
        )
        conn.execute('CREATE INDEX IF NOT EXISTS idx_safety_runaway_tenant_seq ON safety_runaway_loop_history(tenant_id, seq DESC)')

    @staticmethod
    def _migrate_v2(conn: Connection) -> None:
        cols = {str(row[1]) for row in conn.execute('PRAGMA table_info(safety_runaway_loop_history)').fetchall()}
        if 'observed_at' not in cols:
            conn.execute("ALTER TABLE safety_runaway_loop_history ADD COLUMN observed_at TEXT NOT NULL DEFAULT ''")

    def append(self, tenant_id: str, fingerprint: str) -> tuple[str, ...]:
        tenant_key = str(tenant_id).strip() or 'unknown'
        fp = str(fingerprint).strip()
        if not fp:
            raise ValueError('fingerprint is required')
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO safety_runaway_loop_history(tenant_id, fingerprint, observed_at) VALUES (?, ?, datetime('now'))",
                (tenant_key, fp),
            )
            rows = conn.execute(
                'SELECT seq, fingerprint FROM safety_runaway_loop_history WHERE tenant_id = ? ORDER BY seq DESC LIMIT ?',
                (tenant_key, self._maxlen),
            ).fetchall()
            if len(rows) >= self._maxlen:
                floor_seq = int(rows[-1][0])
                conn.execute(
                    'DELETE FROM safety_runaway_loop_history WHERE tenant_id = ? AND seq < ?',
                    (tenant_key, floor_seq),
                )
        return tuple(str(row[1]) for row in reversed(rows))


__all__ = [
    'CANON_SAFETY_RUNAWAY_LOOP_STORE',
    'InMemoryRunawayLoopStore',
    'RunawayLoopStore',
    'SqliteRunawayLoopStore',
]
