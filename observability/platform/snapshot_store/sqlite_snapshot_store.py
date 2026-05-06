from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Optional

from storage.sqlite_fallback import SqliteSessionFactory
from storage.tenant_partitioning import build_partition_key, normalize_storage_tenant_id


CANON_SQLITE_SNAPSHOT_STORE = True


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(bytes(data)).hexdigest()


class SqliteSnapshotStore:
    """Dev snapshot store with stronger metadata and storage hardening."""

    def __init__(self, path: str, *, tenant_id: str | None = None):
        self._path = str(path)
        self._tenant_id = normalize_storage_tenant_id(tenant_id)
        self._partition_key = build_partition_key(self._tenant_id, scope="snapshot_store")
        self._session_factory = SqliteSessionFactory(self._path, wal=True, busy_timeout_ms=5000, synchronous="NORMAL")
        self._session = None

    def __enter__(self):
        self._session = self._session_factory.open().__enter__()
        self._init_schema()
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._session is not None:
            self._session.__exit__(exc_type, exc, tb)
            self._session = None

    @property
    def _db(self):
        if self._session is None:
            raise RuntimeError("sqlite snapshot store is not open")
        return self._session

    def _init_schema(self) -> None:
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS snapshots (
                snapshot_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                partition_key TEXT NOT NULL,
                canonical_bytes BLOB NOT NULL,
                content_sha256 TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_partition_key ON snapshots(partition_key)")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_tenant_id ON snapshots(tenant_id)")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_updated_at ON snapshots(updated_at)")
        self._db.commit()

    def put(self, snapshot_id: str, canonical_bytes: bytes) -> None:
        data = bytes(canonical_bytes)
        now_iso = _utc_now_iso()
        self._db.execute(
            """
            INSERT INTO snapshots(
                snapshot_id,
                tenant_id,
                partition_key,
                canonical_bytes,
                content_sha256,
                size_bytes,
                created_at,
                updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(snapshot_id) DO UPDATE SET
                tenant_id=excluded.tenant_id,
                partition_key=excluded.partition_key,
                canonical_bytes=excluded.canonical_bytes,
                content_sha256=excluded.content_sha256,
                size_bytes=excluded.size_bytes,
                updated_at=excluded.updated_at
            """,
            (
                str(snapshot_id),
                self._tenant_id,
                self._partition_key,
                data,
                _sha256_hex(data),
                len(data),
                now_iso,
                now_iso,
            ),
        )
        self._db.commit()

    def get(self, snapshot_id: str) -> Optional[bytes]:
        row = self._db.fetchone("SELECT canonical_bytes FROM snapshots WHERE snapshot_id = ?", (str(snapshot_id),))
        return None if row is None or row[0] is None else bytes(row[0])

    def ping(self) -> bool:
        try:
            return self._db.fetchone("SELECT 1") is not None
        except Exception:
            return False
