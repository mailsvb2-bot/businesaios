from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timezone
from typing import Any, Mapping

from runtime.business_autonomy.distributed_state import FileDistributedDocumentStore

CANON_PLATFORM_ADMIN_SNAPSHOT_STORE = True


def _now_text() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class FilePlatformAdminSnapshotStore:
    documents: FileDistributedDocumentStore
    collection: str = "platform_admin_snapshots"
    history_collection: str = "platform_admin_snapshot_history"

    def write_snapshot(self, *, snapshot_name: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        key = str(snapshot_name).strip() or 'default'
        current = self.documents.get(collection=self.collection, document_id=key)
        expected_version = None if current is None else int(current.get('version') or 0)
        body = {
            'snapshot_name': key,
            'captured_at_utc': str(payload.get('captured_at_utc') or _now_text()),
            'risk_rows': [dict(item) for item in list(payload.get('risk_rows') or [])],
            'severity_counts': dict(payload.get('severity_counts') or {}),
            'risk_digest': dict(payload.get('risk_digest') or {}),
            'summary_cards': [dict(item) for item in list(payload.get('summary_cards') or [])],
            'trend_metrics': dict(payload.get('trend_metrics') or {}),
            'block_rows': [dict(item) for item in list(payload.get('block_rows') or [])],
        }
        self.documents.put(collection=self.collection, document_id=key, payload=body, expected_version=expected_version)
        self._append_history(snapshot_name=key, payload=body)
        return self.read_snapshot(snapshot_name=key) or body

    def read_snapshot(self, *, snapshot_name: str) -> dict[str, Any] | None:
        item = self.documents.get(collection=self.collection, document_id=str(snapshot_name).strip() or 'default')
        return None if item is None else dict(item)

    def list_history(self, *, snapshot_name: str, limit: int = 20) -> tuple[dict[str, Any], ...]:
        prefix = f"{str(snapshot_name).strip() or 'default'}:"
        rows = self.documents.list_prefix(collection=self.history_collection, prefix=prefix, limit=max(1, int(limit)))
        return tuple(dict(item) for item in rows)

    def _append_history(self, *, snapshot_name: str, payload: Mapping[str, Any]) -> None:
        captured_at = str(payload.get('captured_at_utc') or _now_text())
        history_id = f"{snapshot_name}:{captured_at}"
        self.documents.put(
            collection=self.history_collection,
            document_id=history_id,
            payload={
                'snapshot_name': snapshot_name,
                'captured_at_utc': captured_at,
                'risk_rows': [dict(item) for item in list(payload.get('risk_rows') or [])],
                'severity_counts': dict(payload.get('severity_counts') or {}),
                'risk_digest': dict(payload.get('risk_digest') or {}),
                'summary_cards': [dict(item) for item in list(payload.get('summary_cards') or [])],
                'trend_metrics': dict(payload.get('trend_metrics') or {}),
                'block_rows': [dict(item) for item in list(payload.get('block_rows') or [])],
            },
            expected_version=None,
        )


__all__ = ['CANON_PLATFORM_ADMIN_SNAPSHOT_STORE', 'FilePlatformAdminSnapshotStore']
