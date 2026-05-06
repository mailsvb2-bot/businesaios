from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Protocol, Sequence

from governance.control_plane_audit_log import GovernanceAuditEvent
from storage.evidence_store import EvidenceRecord
from storage.tenant_partitioning import build_partition_key, normalize_storage_tenant_id


CANON_DISTRIBUTED_EVIDENCE_AUDIT_BACKEND = True


class EvidenceAppendPort(Protocol):
    def append(self, *, partition_key: str, payload: Mapping[str, Any]) -> str: ...
    def read_partition(self, *, partition_key: str, limit: int = 100, cursor: str | None = None) -> tuple[Sequence[Mapping[str, Any]], str | None]: ...
    def read_prefix(self, *, prefix: str, limit: int = 100, cursor: str | None = None) -> tuple[Sequence[Mapping[str, Any]], str | None]: ...


class DistributedEvidenceStore:
    def __init__(self, append_port: EvidenceAppendPort) -> None:
        self._append_port = append_port

    def append(self, record: EvidenceRecord) -> EvidenceRecord:
        normalized = record.normalized()
        self._append_port.append(partition_key=normalized.partition_key, payload=normalized.to_row())
        return normalized

    def list_for_tenant(self, *, tenant_id: str, limit: int = 100, cursor: str | None = None) -> tuple[tuple[EvidenceRecord, ...], str | None]:
        tenant = normalize_storage_tenant_id(tenant_id)
        rows, next_cursor = self._append_port.read_prefix(prefix="evidence_", limit=limit, cursor=cursor)
        filtered = [row for row in rows if str(row.get("tenant_id") or tenant) == tenant]
        return tuple(EvidenceRecord.from_row(row) for row in filtered), next_cursor


@dataclass(frozen=True)
class DistributedAuditCursorPage:
    events: tuple[GovernanceAuditEvent, ...]
    next_cursor: str | None = None


class DistributedGovernanceAuditLog:
    def __init__(self, append_port: EvidenceAppendPort, *, partition_prefix: str = "governance_audit") -> None:
        self._append_port = append_port
        self._partition_prefix = str(partition_prefix).strip() or "governance_audit"

    def append(self, event: GovernanceAuditEvent) -> str:
        partition_key = build_partition_key(event.tenant_id, scope=self._partition_prefix)
        return self._append_port.append(
            partition_key=partition_key,
            payload={
                "event_type": event.event_type,
                "tenant_id": event.tenant_id,
                "payload": dict(event.payload),
                "emitted_at": event.emitted_at.isoformat(),
            },
        )

    def read_events(self, *, tenant_id: str, limit: int = 100, cursor: str | None = None) -> DistributedAuditCursorPage:
        rows, next_cursor = self._append_port.read_partition(
            partition_key=build_partition_key(tenant_id, scope=self._partition_prefix),
            limit=limit,
            cursor=cursor,
        )
        events = tuple(
            GovernanceAuditEvent(
                event_type=str(row.get("event_type") or "unknown"),
                tenant_id=str(row.get("tenant_id") or tenant_id),
                payload=dict(row.get("payload") or {}),
                emitted_at=datetime.fromisoformat(str(row.get("emitted_at"))),
            )
            for row in rows
        )
        return DistributedAuditCursorPage(events=events, next_cursor=next_cursor)


__all__ = [
    "CANON_DISTRIBUTED_EVIDENCE_AUDIT_BACKEND",
    "DistributedAuditCursorPage",
    "DistributedEvidenceStore",
    "DistributedGovernanceAuditLog",
    "EvidenceAppendPort",
]
