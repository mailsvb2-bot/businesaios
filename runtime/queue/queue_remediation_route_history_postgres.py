from __future__ import annotations

"""Postgres-backed route history for queue remediation surfaces."""

from dataclasses import dataclass
from datetime import datetime
import json

from runtime.platform.postgres_port import PostgresPort
from runtime.queue.job_contract import normalize_now
from runtime.queue.queue_remediation_route_history_sqlite import QueueRemediationRouteHistoryEntry

CANON_RUNTIME_QUEUE_REMEDIATION_ROUTE_HISTORY_POSTGRES = True

@dataclass
class PostgresQueueRemediationRouteHistoryStore:
    dsn: str
    application_name: str = 'businesaios-queue-remediation-route-history'

    def __post_init__(self) -> None:
        self._port: PostgresPort | None = None

    def __enter__(self) -> 'PostgresQueueRemediationRouteHistoryStore':
        self._port = PostgresPort(self.dsn, application_name=self.application_name).__enter__()
        self._init_schema()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        assert self._port is not None
        self._port.__exit__(exc_type, exc, tb)
        self._port = None

    def record(self, *, tenant_id: str, queue_name: str, action: str, source: str, status: str, metadata: dict[str, object], actor_id: str | None = None, request_id: str | None = None, recorded_at: datetime | None = None) -> QueueRemediationRouteHistoryEntry:
        entry = QueueRemediationRouteHistoryEntry(
            tenant_id=str(tenant_id).strip(), queue_name=str(queue_name).strip(), action=str(action).strip(), source=str(source).strip() or 'control_plane', actor_id=(str(actor_id).strip() or None) if actor_id is not None else None, request_id=(str(request_id).strip() or None) if request_id is not None else None, status=str(status).strip() or 'ok', metadata=dict(metadata), recorded_at=normalize_now(recorded_at)
        )
        port = self._require_port()
        port.execute("INSERT INTO runtime_queue_remediation_route_history (tenant_id, queue_name, action, source, actor_id, request_id, status, metadata_json, recorded_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);", (entry.tenant_id, entry.queue_name, entry.action, entry.source, entry.actor_id, entry.request_id, entry.status, json.dumps(entry.metadata, ensure_ascii=False, separators=(',', ':')), entry.recorded_at.isoformat()))
        port.commit()
        return entry

    def list_entries(self, *, tenant_id: str, queue_name: str, limit: int = 50) -> tuple[QueueRemediationRouteHistoryEntry, ...]:
        rows = self._require_port().fetchall("SELECT tenant_id, queue_name, action, source, actor_id, request_id, status, metadata_json, recorded_at FROM runtime_queue_remediation_route_history WHERE tenant_id = %s AND queue_name = %s ORDER BY id DESC LIMIT %s;", (str(tenant_id).strip(), str(queue_name).strip(), max(0, int(limit))))
        return tuple(QueueRemediationRouteHistoryEntry(tenant_id=str(r[0]), queue_name=str(r[1]), action=str(r[2]), source=str(r[3]), actor_id=None if r[4] is None else str(r[4]), request_id=None if r[5] is None else str(r[5]), status=str(r[6]), metadata=dict(json.loads(str(r[7]) or '{}')), recorded_at=normalize_now(datetime.fromisoformat(str(r[8])))) for r in rows)

    def _init_schema(self) -> None:
        port = self._require_port()
        port.execute("CREATE TABLE IF NOT EXISTS runtime_queue_remediation_route_history (id BIGSERIAL PRIMARY KEY, tenant_id TEXT NOT NULL, queue_name TEXT NOT NULL, action TEXT NOT NULL, source TEXT NOT NULL, actor_id TEXT, request_id TEXT, status TEXT NOT NULL, metadata_json TEXT NOT NULL, recorded_at TEXT NOT NULL);")
        port.execute("CREATE INDEX IF NOT EXISTS ix_runtime_queue_remediation_route_history_lookup ON runtime_queue_remediation_route_history (tenant_id, queue_name, action, recorded_at);")
        port.commit()

    def _require_port(self) -> PostgresPort:
        if self._port is None:
            raise RuntimeError('PostgresQueueRemediationRouteHistoryStore is not open')
        return self._port

__all__ = ['CANON_RUNTIME_QUEUE_REMEDIATION_ROUTE_HISTORY_POSTGRES', 'PostgresQueueRemediationRouteHistoryStore']
