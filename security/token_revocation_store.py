from __future__ import annotations

import sqlite3
import time
from pathlib import Path


CANON_TOKEN_REVOCATION_STORE = True


class SQLiteTokenRevocationStore:
    """Durable owner of revoked token fingerprints."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._ensure_schema()

    def revoke(self, *, token_fingerprint: str, reason: str) -> None:
        now = int(time.time())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO token_revocations(token_fingerprint, reason, revoked_at_epoch_s)
                VALUES(?, ?, ?)
                """,
                (str(token_fingerprint), str(reason), now),
            )
            conn.commit()

    def is_revoked(self, *, token_fingerprint: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                'SELECT token_fingerprint FROM token_revocations WHERE token_fingerprint = ?',
                (str(token_fingerprint),),
            ).fetchone()
        return row is not None

    def _ensure_schema(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS token_revocations (
                    token_fingerprint TEXT PRIMARY KEY,
                    reason TEXT NOT NULL,
                    revoked_at_epoch_s INTEGER NOT NULL
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
    'CANON_TOKEN_REVOCATION_STORE',
    'SQLiteTokenRevocationStore',
]
