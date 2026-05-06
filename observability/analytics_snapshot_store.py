from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from storage.sqlite_fallback import SqliteSessionFactory
from storage.tenant_partitioning import build_partition_key, normalize_storage_tenant_id


@dataclass(frozen=True)
class AnalyticsSnapshotRecord:
    snapshot_id: str
    tenant_id: str
    snapshot_kind: str
    payload: dict[str, Any]
    created_at: str
    content_sha256: str


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _payload_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


class SqliteAnalyticsSnapshotStore:
    def __init__(self, path: str = 'runtime/data/analytics_snapshots.db', *, tenant_id: str | None = None) -> None:
        self._path = str(path)
        self._tenant_id = normalize_storage_tenant_id(tenant_id)
        self._partition_key = build_partition_key(self._tenant_id, scope='analytics_snapshot_store')
        self._session_factory = SqliteSessionFactory(self._path, wal=True, busy_timeout_ms=5000, synchronous='NORMAL')
        self._session = None

    def __enter__(self) -> 'SqliteAnalyticsSnapshotStore':
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
            raise RuntimeError('sqlite analytics snapshot store is not open')
        return self._session

    def _init_schema(self) -> None:
        self._db.execute(
            '''
            CREATE TABLE IF NOT EXISTS analytics_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                partition_key TEXT NOT NULL,
                snapshot_kind TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                content_sha256 TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            '''
        )
        self._db.execute('CREATE INDEX IF NOT EXISTS idx_analytics_snapshots_tenant_id ON analytics_snapshots(tenant_id)')
        self._db.commit()

    def put(self, *, snapshot_id: str, tenant_id: str, snapshot_kind: str, payload: dict[str, Any]) -> AnalyticsSnapshotRecord:
        normalized_tenant_id = normalize_storage_tenant_id(tenant_id)
        partition_key = build_partition_key(normalized_tenant_id, scope='analytics_snapshot_store')
        payload_bytes = _payload_bytes(payload)
        now = _utc_now_iso()
        sha = hashlib.sha256(payload_bytes).hexdigest()
        self._db.execute(
            '''
            INSERT INTO analytics_snapshots(snapshot_id, tenant_id, partition_key, snapshot_kind, payload_json, content_sha256, created_at, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(snapshot_id) DO UPDATE SET
                tenant_id=excluded.tenant_id,
                partition_key=excluded.partition_key,
                snapshot_kind=excluded.snapshot_kind,
                payload_json=excluded.payload_json,
                content_sha256=excluded.content_sha256,
                updated_at=excluded.updated_at
            ''',
            (str(snapshot_id), normalized_tenant_id, partition_key, str(snapshot_kind), payload_bytes.decode('utf-8'), sha, now, now),
        )
        self._db.commit()
        return AnalyticsSnapshotRecord(snapshot_id=str(snapshot_id), tenant_id=normalized_tenant_id, snapshot_kind=str(snapshot_kind), payload=dict(payload), created_at=now, content_sha256=sha)

    def get(self, snapshot_id: str) -> AnalyticsSnapshotRecord | None:
        row = self._db.fetchone('SELECT snapshot_id, tenant_id, snapshot_kind, payload_json, created_at, content_sha256 FROM analytics_snapshots WHERE snapshot_id=?', (str(snapshot_id),))
        if row is None:
            return None
        return AnalyticsSnapshotRecord(snapshot_id=str(row[0]), tenant_id=str(row[1]), snapshot_kind=str(row[2]), payload=json.loads(str(row[3] or '{}')), created_at=str(row[4]), content_sha256=str(row[5]))
