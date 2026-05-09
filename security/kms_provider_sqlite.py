from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from security.kms_provider_contract import KMSKeyHandle, KMSProviderCapability


CANON_SQLITE_KMS_PROVIDER = True


class SQLiteKMSProvider:
    """Durable reference KMS provider backed by its own sqlite registry.

    This avoids introducing a shadow key brain while still providing a real
    persistent provider implementation for governance wiring and tests.
    """

    def __init__(self, db_path: str, *, provider_name: str = 'sqlite-kms', hsm_backed: bool = False) -> None:
        self._db_path = str(db_path)
        self._provider_name = str(provider_name)
        self._hsm_backed = bool(hsm_backed)
        self._ensure_schema()

    def capability(self) -> KMSProviderCapability:
        return KMSProviderCapability(
            provider_name=self._provider_name,
            supports_signing=True,
            supports_encryption=True,
            supports_rotation=True,
            supports_hsm_backed_keys=self._hsm_backed,
        )

    def create_key(self, *, key_id: str, algorithm: str, exportable: bool = False, credential_ref: str | None = None) -> KMSKeyHandle:
        _ = credential_ref
        resolved_key_id = str(key_id).strip()
        resolved_algorithm = str(algorithm).strip()
        if not resolved_key_id:
            raise ValueError('key_id is required')
        if not resolved_algorithm:
            raise ValueError('algorithm is required')
        version = self._next_version(key_id=resolved_key_id)
        now = int(time.time())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO kms_provider_keys(
                    key_id, key_version, algorithm, exportable, created_at_epoch_s, active
                ) VALUES(?, ?, ?, ?, ?, 1)
                """,
                (resolved_key_id, version, resolved_algorithm, 1 if exportable else 0, now),
            )
            conn.execute(
                """
                UPDATE kms_provider_keys
                SET active = 0
                WHERE key_id = ? AND key_version != ?
                """,
                (resolved_key_id, version),
            )
            conn.commit()
        return KMSKeyHandle(
            provider_name=self._provider_name,
            key_id=resolved_key_id,
            key_version=version,
            algorithm=resolved_algorithm,
            exportable=bool(exportable),
        )

    def get_active_key(self, *, key_id: str, credential_ref: str | None = None) -> KMSKeyHandle:
        _ = credential_ref
        resolved_key_id = str(key_id).strip()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT key_version, algorithm, exportable
                FROM kms_provider_keys
                WHERE key_id = ? AND active = 1
                ORDER BY key_version DESC
                LIMIT 1
                """,
                (resolved_key_id,),
            ).fetchone()
        if row is None:
            return self.create_key(key_id=resolved_key_id, algorithm='aes256_gcm', exportable=False, credential_ref=credential_ref)
        return KMSKeyHandle(
            provider_name=self._provider_name,
            key_id=resolved_key_id,
            key_version=int(row[0]),
            algorithm=str(row[1]),
            exportable=bool(int(row[2])),
        )

    def _next_version(self, *, key_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT MAX(key_version) FROM kms_provider_keys WHERE key_id = ?",
                (str(key_id),),
            ).fetchone()
        return (int(row[0]) if row and row[0] is not None else 0) + 1

    def _ensure_schema(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS kms_provider_keys (
                    key_id TEXT NOT NULL,
                    key_version INTEGER NOT NULL,
                    algorithm TEXT NOT NULL,
                    exportable INTEGER NOT NULL,
                    created_at_epoch_s INTEGER NOT NULL,
                    active INTEGER NOT NULL,
                    PRIMARY KEY(key_id, key_version)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_kms_provider_keys_lookup
                ON kms_provider_keys(key_id, active, key_version)
                """
            )
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=NORMAL')
        return conn


__all__ = [
    'CANON_SQLITE_KMS_PROVIDER',
    'SQLiteKMSProvider',
]
