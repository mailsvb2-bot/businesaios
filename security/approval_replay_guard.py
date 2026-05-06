from __future__ import annotations

import sqlite3
import time
from pathlib import Path


CANON_SECURITY_APPROVAL_REPLAY_GUARD = True


class SQLiteApprovalReplayGuard:
    """Durable single-use approval guard.

    Prevents replay of previously consumed signed approvals for high-risk operations.
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._ensure_schema()

    def consume(self, *, approval_id: str, operation_kind: str, actor: str) -> bool:
        now = int(time.time())
        with self._connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute(
                "SELECT approval_id FROM consumed_operator_approvals WHERE approval_id = ?",
                (str(approval_id),),
            ).fetchone()
            if row is not None:
                conn.rollback()
                return False
            conn.execute(
                """
                INSERT INTO consumed_operator_approvals(
                    approval_id,
                    operation_kind,
                    actor,
                    consumed_at_epoch_s
                ) VALUES(?, ?, ?, ?)
                """,
                (str(approval_id), str(operation_kind), str(actor), now),
            )
            conn.commit()
            return True

    def has_been_consumed(self, *, approval_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT approval_id FROM consumed_operator_approvals WHERE approval_id = ?",
                (str(approval_id),),
            ).fetchone()
        return row is not None

    def _ensure_schema(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS consumed_operator_approvals (
                    approval_id TEXT PRIMARY KEY,
                    operation_kind TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    consumed_at_epoch_s INTEGER NOT NULL
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
    'CANON_SECURITY_APPROVAL_REPLAY_GUARD',
    'SQLiteApprovalReplayGuard',
]
