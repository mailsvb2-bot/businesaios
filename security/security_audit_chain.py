from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Mapping


CANON_SECURITY_AUDIT_CHAIN = True


class SQLiteSecurityAuditChain:
    """Tamper-evident chained audit log for security events."""

    def __init__(self, db_path: str) -> None:
        self._db_path = str(db_path)
        self._ensure_schema()

    def append(self, *, event_kind: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        now = int(time.time())
        payload_json = json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        with self._connect() as conn:
            row = conn.execute(
                "SELECT event_hash FROM security_audit_chain ORDER BY event_id DESC LIMIT 1"
            ).fetchone()
            previous_hash = str(row[0]) if row else 'GENESIS'
            body = f'{previous_hash}|{event_kind}|{payload_json}|{now}'
            event_hash = hashlib.sha256(body.encode('utf-8')).hexdigest()
            cursor = conn.execute(
                """
                INSERT INTO security_audit_chain(event_kind, payload_json, previous_hash, event_hash, created_at_epoch_s)
                VALUES(?, ?, ?, ?, ?)
                """,
                (str(event_kind), payload_json, previous_hash, event_hash, now),
            )
            conn.commit()
            return {
                'event_id': int(cursor.lastrowid),
                'previous_hash': previous_hash,
                'event_hash': event_hash,
                'created_at_epoch_s': now,
            }

    def verify_chain(self) -> dict[str, Any]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT event_id, event_kind, payload_json, previous_hash, event_hash, created_at_epoch_s FROM security_audit_chain ORDER BY event_id ASC"
            ).fetchall()
        expected_previous = 'GENESIS'
        violations: list[str] = []
        for row in rows:
            event_id = int(row[0])
            event_kind = str(row[1])
            payload_json = str(row[2])
            previous_hash = str(row[3])
            event_hash = str(row[4])
            created_at_epoch_s = int(row[5])
            if previous_hash != expected_previous:
                violations.append(f'chain_break:{event_id}')
            body = f'{previous_hash}|{event_kind}|{payload_json}|{created_at_epoch_s}'
            recomputed = hashlib.sha256(body.encode('utf-8')).hexdigest()
            if recomputed != event_hash:
                violations.append(f'hash_mismatch:{event_id}')
            expected_previous = event_hash
        return {'ok': len(violations) == 0, 'violations': violations, 'events_checked': len(rows)}

    def _ensure_schema(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS security_audit_chain (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_kind TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL,
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
    'CANON_SECURITY_AUDIT_CHAIN',
    'SQLiteSecurityAuditChain',
]
