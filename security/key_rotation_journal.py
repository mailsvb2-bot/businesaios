from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Mapping


CANON_KEY_ROTATION_JOURNAL = True


class SQLiteKeyRotationJournal:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._ensure_schema()

    def append(self, *, key_id: str, old_status: str, new_status: str, payload: Mapping[str, Any]) -> None:
        now = int(time.time())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO key_rotation_journal(key_id, old_status, new_status, payload_json, created_at_epoch_s)
                VALUES(?, ?, ?, ?, ?)
                """,
                (str(key_id), str(old_status), str(new_status), json.dumps(dict(payload), ensure_ascii=False), now),
            )
            conn.commit()

    def latest(self, *, limit: int = 50) -> list[dict[str, Any]]:
        resolved = max(int(limit), 1)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT key_id, old_status, new_status, payload_json, created_at_epoch_s FROM key_rotation_journal ORDER BY journal_id DESC LIMIT ?",
                (resolved,),
            ).fetchall()
        return [
            {
                'key_id': str(row[0]),
                'old_status': str(row[1]),
                'new_status': str(row[2]),
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
                CREATE TABLE IF NOT EXISTS key_rotation_journal (
                    journal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key_id TEXT NOT NULL,
                    old_status TEXT NOT NULL,
                    new_status TEXT NOT NULL,
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
    'CANON_KEY_ROTATION_JOURNAL',
    'SQLiteKeyRotationJournal',
]
