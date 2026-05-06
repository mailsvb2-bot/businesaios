from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Optional

from storage.postgres_session import PostgresSessionFactory
from storage.tenant_partitioning import build_partition_key, normalize_storage_tenant_id


CANON_POSTGRES_SNAPSHOT_STORE = True


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(bytes(data)).hexdigest()


class PostgresSnapshotStore:
    def __init__(self, dsn: str, *, tenant_id: str | None = None):
        self._dsn = str(dsn)
        self._tenant_id = normalize_storage_tenant_id(tenant_id)
        self._partition_key = build_partition_key(self._tenant_id, scope="snapshot_store")
        self._session_factory = PostgresSessionFactory(
            self._dsn,
            application_name="businesaios-snapshots",
            statement_timeout_ms=30000,
            lock_timeout_ms=5000,
        )
        self._session = None

    def __enter__(self) -> "PostgresSnapshotStore":
        self._session = self._session_factory.open().__enter__()
        self._init_schema()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._session is not None:
            self._session.__exit__(exc_type, exc, tb)
            self._session = None

    @property
    def _db(self):
        if self._session is None:
            raise RuntimeError("postgres snapshot store is not open")
        return self._session

    def _init_schema(self) -> None:
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS snapshots (
                snapshot_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                partition_key TEXT NOT NULL,
                canonical_bytes BYTEA NOT NULL,
                content_sha256 TEXT NOT NULL,
                size_bytes BIGINT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL
            );
            """
        )
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_partition_key ON snapshots(partition_key);")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_tenant_id ON snapshots(tenant_id);")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_updated_at ON snapshots(updated_at);")
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
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (snapshot_id) DO UPDATE SET
                tenant_id=EXCLUDED.tenant_id,
                partition_key=EXCLUDED.partition_key,
                canonical_bytes=EXCLUDED.canonical_bytes,
                content_sha256=EXCLUDED.content_sha256,
                size_bytes=EXCLUDED.size_bytes,
                updated_at=EXCLUDED.updated_at;
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
        row = self._db.fetchone(
            "SELECT canonical_bytes FROM snapshots WHERE snapshot_id=%s LIMIT 1;",
            (str(snapshot_id),),
        )
        if not row:
            return None
        value = row.get("canonical_bytes")
        return None if value is None else bytes(value)

    def ping(self) -> bool:
        try:
            return self._db.fetchone("SELECT 1 AS ok;") is not None
        except Exception:
            return False
