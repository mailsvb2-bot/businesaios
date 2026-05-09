from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Mapping


CANON_SECURITY_QUARANTINE_REGISTRY = True


class SQLiteSecurityQuarantineRegistry:
    """Durable owner of compromised/quarantined security entities."""

    def __init__(self, db_path: str) -> None:
        self._db_path = str(db_path)
        self._ensure_schema()

    def quarantine(self, *, entity_kind: str, entity_id: str, reason: str, payload: Mapping[str, Any] | None = None) -> None:
        now = int(time.time())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO security_quarantine(
                    entity_kind, entity_id, reason, payload_json, quarantined_at_epoch_s, released_at_epoch_s
                ) VALUES(?, ?, ?, ?, ?, NULL)
                """,
                (str(entity_kind), str(entity_id), str(reason), json.dumps(dict(payload or {}), ensure_ascii=False), now),
            )
            conn.commit()

    def release(self, *, entity_kind: str, entity_id: str) -> bool:
        now = int(time.time())
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE security_quarantine
                SET released_at_epoch_s = ?
                WHERE entity_kind = ? AND entity_id = ? AND released_at_epoch_s IS NULL
                """,
                (now, str(entity_kind), str(entity_id)),
            )
            conn.commit()
            return int(cursor.rowcount) > 0

    def is_quarantined(self, *, entity_kind: str, entity_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT entity_id FROM security_quarantine WHERE entity_kind = ? AND entity_id = ? AND released_at_epoch_s IS NULL",
                (str(entity_kind), str(entity_id)),
            ).fetchone()
        return row is not None

    def count_active(self, *, entity_kind: str | None = None) -> int:
        with self._connect() as conn:
            if entity_kind is None:
                row = conn.execute(
                    "SELECT COUNT(*) FROM security_quarantine WHERE released_at_epoch_s IS NULL"
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT COUNT(*) FROM security_quarantine WHERE entity_kind = ? AND released_at_epoch_s IS NULL",
                    (str(entity_kind),),
                ).fetchone()
        return int(row[0] if row else 0)

    def _ensure_schema(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS security_quarantine (
                    entity_kind TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    quarantined_at_epoch_s INTEGER NOT NULL,
                    released_at_epoch_s INTEGER NULL,
                    PRIMARY KEY(entity_kind, entity_id)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_security_quarantine_active ON security_quarantine(entity_kind, released_at_epoch_s)"
            )
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=NORMAL')
        return conn


__all__ = [
    'CANON_SECURITY_QUARANTINE_REGISTRY',
    'SQLiteSecurityQuarantineRegistry',
]
