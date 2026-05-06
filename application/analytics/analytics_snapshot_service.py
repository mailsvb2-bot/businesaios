from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from typing import Any

from observability.analytics_snapshot_store import AnalyticsSnapshotRecord, SqliteAnalyticsSnapshotStore


def _to_plain_payload(value: Any) -> dict[str, Any]:
    if is_dataclass(value):
        return json.loads(json.dumps(asdict(value), ensure_ascii=False))
    if isinstance(value, dict):
        return json.loads(json.dumps(value, ensure_ascii=False))
    raise TypeError('analytics snapshot payload must be a dataclass or dict')


def _stable_snapshot_id(tenant_id: str, snapshot_kind: str, payload: dict[str, Any]) -> str:
    canonical = json.dumps({'tenant_id': str(tenant_id), 'snapshot_kind': str(snapshot_kind), 'payload': payload}, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    return f"analytics-{snapshot_kind}-{hashlib.sha256(canonical).hexdigest()[:24]}"


class AnalyticsSnapshotService:
    def __init__(self, store: SqliteAnalyticsSnapshotStore) -> None:
        self._store = store

    def write_snapshot(self, *, tenant_id: str, snapshot_kind: str, payload: Any, snapshot_id: str | None = None) -> AnalyticsSnapshotRecord:
        plain = _to_plain_payload(payload)
        return self._store.put(snapshot_id=str(snapshot_id or _stable_snapshot_id(tenant_id, snapshot_kind, plain)), tenant_id=str(tenant_id), snapshot_kind=str(snapshot_kind), payload=plain)

    def read_snapshot(self, *, snapshot_id: str) -> AnalyticsSnapshotRecord | None:
        return self._store.get(snapshot_id)
