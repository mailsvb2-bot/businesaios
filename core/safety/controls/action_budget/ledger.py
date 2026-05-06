from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from sqlite3 import Connection
from threading import RLock
from typing import Iterator, Protocol

from ..support.sqlite_migrations import SafetySqliteMigrator, SchemaMigrationPlan

CANON_SAFETY_ACTION_BUDGET_LEDGER = True
SCHEMA_VERSION = 2


class ActionBudgetLedger(Protocol):
    def snapshot(self, tenant_id: str) -> tuple[float, int]: ...

    def record(self, tenant_id: str, *, estimated_cost: float) -> None: ...


@dataclass
class InMemoryActionBudgetLedger:
    cost_by_tenant: dict[str, float] = field(default_factory=dict)
    actions_by_tenant: dict[str, int] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock)

    def snapshot(self, tenant_id: str) -> tuple[float, int]:
        with self._lock:
            return float(self.cost_by_tenant.get(str(tenant_id), 0.0)), int(self.actions_by_tenant.get(str(tenant_id), 0))

    def record(self, tenant_id: str, *, estimated_cost: float) -> None:
        with self._lock:
            key = str(tenant_id)
            self.cost_by_tenant[key] = float(self.cost_by_tenant.get(key, 0.0)) + float(estimated_cost)
            self.actions_by_tenant[key] = int(self.actions_by_tenant.get(key, 0)) + 1


class SqliteActionBudgetLedger:
    def __init__(self, *, sqlite_path: str) -> None:
        self._path = str(sqlite_path).strip()
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
        plan = SchemaMigrationPlan(component='action_budget_ledger', target_version=SCHEMA_VERSION, steps=(self._migrate_v1, self._migrate_v2))
        with self._connect() as conn:
            SafetySqliteMigrator().apply(conn, plan)

    @staticmethod
    def _migrate_v1(conn: Connection) -> None:
        conn.execute(
            '''
            CREATE TABLE IF NOT EXISTS safety_action_budget_ledger (
                tenant_id TEXT PRIMARY KEY,
                total_cost REAL NOT NULL,
                total_actions INTEGER NOT NULL
            )
            '''
        )

    @staticmethod
    def _migrate_v2(conn: Connection) -> None:
        cols = {str(row[1]) for row in conn.execute('PRAGMA table_info(safety_action_budget_ledger)').fetchall()}
        if 'updated_at' not in cols:
            conn.execute("ALTER TABLE safety_action_budget_ledger ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''")

    def snapshot(self, tenant_id: str) -> tuple[float, int]:
        key = str(tenant_id).strip() or 'unknown'
        with self._connect() as conn:
            row = conn.execute(
                'SELECT total_cost, total_actions FROM safety_action_budget_ledger WHERE tenant_id = ?',
                (key,),
            ).fetchone()
        if row is None:
            return 0.0, 0
        return float(row[0] or 0.0), int(row[1] or 0)

    def record(self, tenant_id: str, *, estimated_cost: float) -> None:
        key = str(tenant_id).strip() or 'unknown'
        cost, actions = self.snapshot(key)
        with self._connect() as conn:
            conn.execute(
                '''
                INSERT INTO safety_action_budget_ledger(tenant_id, total_cost, total_actions, updated_at)
                VALUES (?, ?, ?, datetime('now'))
                ON CONFLICT(tenant_id) DO UPDATE SET total_cost = excluded.total_cost, total_actions = excluded.total_actions, updated_at = excluded.updated_at
                ''',
                (key, float(cost + float(estimated_cost)), int(actions + 1)),
            )


__all__ = [
    'ActionBudgetLedger',
    'CANON_SAFETY_ACTION_BUDGET_LEDGER',
    'InMemoryActionBudgetLedger',
    'SqliteActionBudgetLedger',
]
