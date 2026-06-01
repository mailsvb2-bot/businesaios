from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from storage.sqlite_fallback import SqliteSessionFactory


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ManifestChainRecord:
    export_id: str
    tenant_id: str
    manifest_sha256: str
    previous_manifest_sha256: str | None
    created_at: str


class SqliteAnalyticsManifestChainStore:
    def __init__(self, path: str = "runtime/data/analytics_manifest_chain.db") -> None:
        self._path = str(path)
        self._session_factory = SqliteSessionFactory(self._path, wal=True, busy_timeout_ms=5000, synchronous="NORMAL")
        self._session = None

    def __enter__(self) -> SqliteAnalyticsManifestChainStore:
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
            raise RuntimeError("analytics manifest chain store is not open")
        return self._session

    def _init_schema(self) -> None:
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS analytics_manifest_chain (
                export_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                manifest_sha256 TEXT NOT NULL,
                previous_manifest_sha256 TEXT,
                created_at TEXT NOT NULL
            )
        """)
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_analytics_manifest_chain_tenant ON analytics_manifest_chain(tenant_id, created_at)")
        self._db.commit()

    def latest_manifest_sha(self, *, tenant_id: str) -> str | None:
        row = self._db.fetchone("SELECT manifest_sha256 FROM analytics_manifest_chain WHERE tenant_id = ? ORDER BY created_at DESC LIMIT 1", (str(tenant_id),))
        return None if row is None else str(row[0])

    def put(self, *, export_id: str, tenant_id: str, manifest_payload: dict[str, Any], created_at: str) -> ManifestChainRecord:
        manifest_json = json.dumps(manifest_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        manifest_sha = _sha256_text(manifest_json)
        previous_sha = self.latest_manifest_sha(tenant_id=str(tenant_id))
        self._db.execute(
            "INSERT OR REPLACE INTO analytics_manifest_chain(export_id, tenant_id, manifest_sha256, previous_manifest_sha256, created_at) VALUES(?, ?, ?, ?, ?)",
            (str(export_id), str(tenant_id), manifest_sha, previous_sha, str(created_at)),
        )
        self._db.commit()
        return ManifestChainRecord(export_id=str(export_id), tenant_id=str(tenant_id), manifest_sha256=manifest_sha, previous_manifest_sha256=previous_sha, created_at=str(created_at))
