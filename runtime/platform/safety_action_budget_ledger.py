from __future__ import annotations

import sqlite3
from math import isfinite
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from sqlite3 import Connection

from runtime.platform.safety_sqlite_migrations import SafetySqliteMigrator, SchemaMigrationPlan

CANON_PLATFORM_SAFETY_ACTION_BUDGET_LEDGER = True
SCHEMA_VERSION = 3


class PlatformSqliteActionBudgetLedger:
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
        plan = SchemaMigrationPlan(
            component='action_budget_ledger',
            target_version=SCHEMA_VERSION,
            steps=(self._migrate_v1, self._migrate_v2, self._migrate_v3),
        )
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

    @staticmethod
    def _migrate_v3(conn: Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS safety_action_budget_ledger_idempotency (
                tenant_id TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                action TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                PRIMARY KEY (tenant_id, idempotency_key)
            )
            """
        )

    @staticmethod
    def _record_total(conn: Connection, tenant_id: str, estimated_cost: float) -> None:
        if not isfinite(float(estimated_cost)) or float(estimated_cost) < 0:
            raise ValueError("action_budget_invalid_cost")
        conn.execute(
            """
            INSERT INTO safety_action_budget_ledger(tenant_id, total_cost, total_actions, updated_at)
            VALUES (?, ?, 1, datetime('now'))
            ON CONFLICT(tenant_id) DO UPDATE SET
                total_cost = safety_action_budget_ledger.total_cost + excluded.total_cost,
                total_actions = safety_action_budget_ledger.total_actions + 1,
                updated_at = excluded.updated_at
            """,
            (tenant_id, float(estimated_cost)),
        )

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
        key = str(tenant_id).strip() or "unknown"
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._record_total(conn, key, float(estimated_cost))

    def recorded_action(self, tenant_id: str, idempotency_key: str) -> tuple[str, str] | None:
        tenant, key = str(tenant_id).strip(), str(idempotency_key).strip()
        if not tenant or not key:
            raise ValueError("tenant_id and idempotency_key are required")
        with self._connect() as conn:
            row = conn.execute(
                "SELECT action,payload_hash FROM safety_action_budget_ledger_idempotency WHERE tenant_id=? AND idempotency_key=?", (tenant, key)).fetchone()
        return (str(row[0]), str(row[1])) if row else None

    def record_once(self, tenant_id: str, *, idempotency_key: str,
                    action: str, payload_hash: str, estimated_cost: float) -> bool:
        tenant, key, action_name, fingerprint = (
            str(tenant_id).strip(), str(idempotency_key).strip(), str(action), str(payload_hash))
        if not tenant or not key:
            raise ValueError("tenant_id and idempotency_key are required")
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT action,payload_hash FROM safety_action_budget_ledger_idempotency WHERE tenant_id=? AND idempotency_key=?", (tenant, key)).fetchone()
            if row:
                if (str(row[0]), str(row[1])) != (action_name, fingerprint):
                    raise RuntimeError("action_budget_idempotency_conflict")
                return False
            conn.execute(
                "INSERT INTO safety_action_budget_ledger_idempotency(tenant_id,idempotency_key,action,payload_hash) VALUES(?,?,?,?)",
                (tenant, key, action_name, fingerprint),
            )
            self._record_total(conn, tenant, float(estimated_cost))
        return True


__all__ = ['CANON_PLATFORM_SAFETY_ACTION_BUDGET_LEDGER', 'PlatformSqliteActionBudgetLedger', 'SCHEMA_VERSION']
