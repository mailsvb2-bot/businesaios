from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Mapping


CANON_SECURITY_AUDIT_EVENT_STORE = True


class SQLiteSecurityAuditEventStore:
    """Durable owner of security audit events before or alongside export."""

    def __init__(self, db_path: str) -> None:
        self._db_path = str(db_path)
        self._ensure_schema()

    def append(self, *, event_kind: str, payload: Mapping[str, Any]) -> int:
        now = int(time.time())
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO security_audit_events(event_kind, payload_json, created_at_epoch_s)
                VALUES(?, ?, ?)
                """,
                (str(event_kind), json.dumps(dict(payload), ensure_ascii=False), now),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def latest(self, *, limit: int = 50) -> list[dict[str, Any]]:
        resolved = max(int(limit), 1)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT event_kind, payload_json, created_at_epoch_s
                FROM security_audit_events
                ORDER BY event_id DESC
                LIMIT ?
                """,
                (resolved,),
            ).fetchall()
        return [
            {
                'event_kind': str(row[0]),
                'payload': json.loads(str(row[1])),
                'created_at_epoch_s': int(row[2]),
            }
            for row in rows
        ]

    def _ensure_schema(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS security_audit_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_kind TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at_epoch_s INTEGER NOT NULL
                )
                """
            )
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=NORMAL')
        return conn


__all__ = [
    'CANON_SECURITY_AUDIT_EVENT_STORE',
    'SQLiteSecurityAuditEventStore',
]
