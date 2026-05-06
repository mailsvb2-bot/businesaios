from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Mapping


CANON_SECURITY_INCIDENT_REGISTRY = True


class SQLiteSecurityIncidentRegistry:
    """Durable owner of security incidents and containment markers."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._ensure_schema()

    def open_incident(self, *, incident_kind: str, payload: Mapping[str, Any]) -> int:
        now = int(time.time())
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO security_incidents(incident_kind, status, payload_json, created_at_epoch_s, resolved_at_epoch_s)
                VALUES(?, 'open', ?, ?, NULL)
                """,
                (str(incident_kind), json.dumps(dict(payload), ensure_ascii=False), now),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def resolve(self, *, incident_id: int, resolution_payload: Mapping[str, Any] | None = None) -> bool:
        now = int(time.time())
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE security_incidents
                SET status = 'resolved',
                    resolution_payload_json = ?,
                    resolved_at_epoch_s = ?
                WHERE incident_id = ?
                  AND status = 'open'
                """,
                (json.dumps(dict(resolution_payload or {}), ensure_ascii=False), now, int(incident_id)),
            )
            conn.commit()
            return int(cursor.rowcount) > 0

    def latest(self, *, limit: int = 50) -> list[dict[str, Any]]:
        resolved = max(int(limit), 1)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT incident_id, incident_kind, status, payload_json, resolution_payload_json, created_at_epoch_s, resolved_at_epoch_s
                FROM security_incidents
                ORDER BY incident_id DESC
                LIMIT ?
                """,
                (resolved,),
            ).fetchall()
        return [
            {
                'incident_id': int(row[0]),
                'incident_kind': str(row[1]),
                'status': str(row[2]),
                'payload': json.loads(str(row[3])),
                'resolution_payload': json.loads(str(row[4] or '{}')),
                'created_at_epoch_s': int(row[5]),
                'resolved_at_epoch_s': None if row[6] is None else int(row[6]),
            }
            for row in rows
        ]

    def _ensure_schema(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS security_incidents (
                    incident_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    incident_kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    resolution_payload_json TEXT NULL,
                    created_at_epoch_s INTEGER NOT NULL,
                    resolved_at_epoch_s INTEGER NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_security_incidents_status_created
                ON security_incidents(status, created_at_epoch_s)
                """
            )
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=NORMAL')
        return conn


__all__ = [
    'CANON_SECURITY_INCIDENT_REGISTRY',
    'SQLiteSecurityIncidentRegistry',
]
