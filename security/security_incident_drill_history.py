from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Mapping


CANON_SECURITY_INCIDENT_DRILL_HISTORY = True


class SQLiteSecurityIncidentDrillHistory:
    """Durable owner of security incident/recovery drills."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._ensure_schema()

    def append(
        self,
        *,
        drill_kind: str,
        ok: bool,
        payload: Mapping[str, Any] | None = None,
    ) -> None:
        now = int(time.time())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO security_incident_drill_history(
                    drill_kind,
                    ok,
                    payload_json,
                    created_at_epoch_s
                ) VALUES(?, ?, ?, ?)
                """,
                (
                    str(drill_kind),
                    1 if ok else 0,
                    json.dumps(dict(payload or {}), ensure_ascii=False),
                    now,
                ),
            )
            conn.commit()

    def latest(self, *, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT drill_kind, ok, payload_json, created_at_epoch_s
                FROM security_incident_drill_history
                ORDER BY drill_id DESC
                LIMIT ?
                """,
                (max(int(limit), 1),),
            ).fetchall()
        return [
            {
                'drill_kind': str(row[0]),
                'ok': bool(int(row[1])),
                'payload': json.loads(str(row[2])),
                'created_at_epoch_s': int(row[3]),
            }
            for row in rows
        ]

    def _ensure_schema(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS security_incident_drill_history (
                    drill_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    drill_kind TEXT NOT NULL,
                    ok INTEGER NOT NULL,
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
    'CANON_SECURITY_INCIDENT_DRILL_HISTORY',
    'SQLiteSecurityIncidentDrillHistory',
]
