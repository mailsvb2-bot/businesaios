from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Mapping


CANON_SECURITY_OPERATOR_WORKFLOW_STORE = True


class SQLiteSecurityOperatorWorkflowStore:
    """Durable owner of operator workflow around sensitive security operations."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._ensure_schema()

    def append_step(
        self,
        *,
        workflow_id: str,
        operation_kind: str,
        actor: str,
        step_kind: str,
        payload: Mapping[str, Any] | None = None,
    ) -> None:
        now = int(time.time())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO security_operator_workflow(
                    workflow_id,
                    operation_kind,
                    actor,
                    step_kind,
                    payload_json,
                    created_at_epoch_s
                ) VALUES(?, ?, ?, ?, ?, ?)
                """,
                (
                    str(workflow_id),
                    str(operation_kind),
                    str(actor),
                    str(step_kind),
                    json.dumps(dict(payload or {}), ensure_ascii=False),
                    now,
                ),
            )
            conn.commit()

    def list_steps(self, *, workflow_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT operation_kind, actor, step_kind, payload_json, created_at_epoch_s
                FROM security_operator_workflow
                WHERE workflow_id = ?
                ORDER BY step_id ASC
                """,
                (str(workflow_id),),
            ).fetchall()
        return [
            {
                'operation_kind': str(row[0]),
                'actor': str(row[1]),
                'step_kind': str(row[2]),
                'payload': json.loads(str(row[3])),
                'created_at_epoch_s': int(row[4]),
            }
            for row in rows
        ]

    def _ensure_schema(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS security_operator_workflow (
                    step_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workflow_id TEXT NOT NULL,
                    operation_kind TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    step_kind TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at_epoch_s INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_security_operator_workflow_lookup
                ON security_operator_workflow(workflow_id, created_at_epoch_s)
                """
            )
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=NORMAL')
        return conn


__all__ = [
    'CANON_SECURITY_OPERATOR_WORKFLOW_STORE',
    'SQLiteSecurityOperatorWorkflowStore',
]
