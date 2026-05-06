from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from sqlite3 import Connection
from threading import RLock
from typing import Iterator, Protocol

from ..support.sqlite_migrations import SafetySqliteMigrator, SchemaMigrationPlan
from .models import CircuitBreakerState

CANON_SAFETY_CIRCUIT_BREAKER_STORE = True
SCHEMA_VERSION = 2


class CircuitBreakerStore(Protocol):
    def get(self, key: str) -> CircuitBreakerState: ...
    def put(self, state: CircuitBreakerState) -> None: ...


@dataclass
class InMemoryCircuitBreakerStore:
    states: dict[str, CircuitBreakerState] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock)

    def get(self, key: str) -> CircuitBreakerState:
        with self._lock:
            return self.states.get(str(key), CircuitBreakerState(key=str(key)))

    def put(self, state: CircuitBreakerState) -> None:
        with self._lock:
            self.states[str(state.key)] = state


class SqliteCircuitBreakerStore:
    def __init__(self, *, sqlite_path: str) -> None:
        raw_path = str(sqlite_path).strip()
        if not raw_path:
            raise ValueError('sqlite_path is required')
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        self._path = str(path)
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self.states = self
        self._init_db()

    @contextmanager
    def _connect(self) -> Iterator[Connection]:
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._path)
        conn.execute('PRAGMA journal_mode = WAL')
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        plan = SchemaMigrationPlan(component='circuit_breaker_states', target_version=SCHEMA_VERSION, steps=(self._migrate_v1, self._migrate_v2))
        with self._connect() as conn:
            SafetySqliteMigrator().apply(conn, plan)

    @staticmethod
    def _migrate_v1(conn: Connection) -> None:
        conn.execute(
            '''
            CREATE TABLE IF NOT EXISTS safety_circuit_breaker_states (
                breaker_key TEXT PRIMARY KEY,
                consecutive_failures INTEGER NOT NULL,
                opened INTEGER NOT NULL
            )
            '''
        )

    @staticmethod
    def _migrate_v2(conn: Connection) -> None:
        cols = {str(row[1]) for row in conn.execute('PRAGMA table_info(safety_circuit_breaker_states)').fetchall()}
        if 'updated_at' not in cols:
            conn.execute("ALTER TABLE safety_circuit_breaker_states ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''")

    def get(self, key: str) -> CircuitBreakerState:
        breaker_key = str(key).strip()
        if not breaker_key:
            raise ValueError('key is required')
        with self._connect() as conn:
            row = conn.execute(
                'SELECT consecutive_failures, opened FROM safety_circuit_breaker_states WHERE breaker_key = ?',
                (breaker_key,),
            ).fetchone()
        if row is None:
            return CircuitBreakerState(key=breaker_key)
        return CircuitBreakerState(
            key=breaker_key,
            consecutive_failures=int(row[0] or 0),
            opened=bool(int(row[1] or 0)),
        )

    def put(self, state: CircuitBreakerState) -> None:
        breaker_key = str(state.key).strip()
        if not breaker_key:
            raise ValueError('state.key is required')
        with self._connect() as conn:
            conn.execute(
                '''
                INSERT INTO safety_circuit_breaker_states(breaker_key, consecutive_failures, opened, updated_at)
                VALUES (?, ?, ?, datetime('now'))
                ON CONFLICT(breaker_key) DO UPDATE SET consecutive_failures = excluded.consecutive_failures, opened = excluded.opened, updated_at = excluded.updated_at
                ''',
                (breaker_key, int(state.consecutive_failures), 1 if state.opened else 0),
            )

    def delete(self, key: str) -> None:
        breaker_key = str(key).strip()
        with self._connect() as conn:
            conn.execute('DELETE FROM safety_circuit_breaker_states WHERE breaker_key = ?', (breaker_key,))

    def clear(self) -> None:
        with self._connect() as conn:
            conn.execute('DELETE FROM safety_circuit_breaker_states')

    def list_keys(self) -> tuple[str, ...]:
        with self._connect() as conn:
            rows = conn.execute('SELECT breaker_key FROM safety_circuit_breaker_states ORDER BY breaker_key ASC').fetchall()
        return tuple(str(row[0]) for row in rows)


__all__ = [
    'CANON_SAFETY_CIRCUIT_BREAKER_STORE',
    'CircuitBreakerStore',
    'InMemoryCircuitBreakerStore',
    'SqliteCircuitBreakerStore',
]
