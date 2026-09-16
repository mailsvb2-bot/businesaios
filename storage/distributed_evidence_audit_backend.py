from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Protocol

from governance.control_plane_audit_log import GovernanceAuditEvent
from storage.evidence_store import EVIDENCE_SCHEMA_VERSION, EvidenceRecord, EvidenceStore
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
        normalized = record.normalized_for_write()
        self._append_port.append(partition_key=normalized.partition_key, payload=normalized.to_row())
        return normalized

    def list_for_tenant(self, *, tenant_id: str, limit: int = 100, cursor: str | None = None) -> tuple[tuple[EvidenceRecord, ...], str | None]:
        raw_tenant = str(tenant_id or "").strip()
        if not raw_tenant:
            raise ValueError("tenant_id is required")
        tenant = normalize_storage_tenant_id(raw_tenant)
        rows, next_cursor = self._append_port.read_prefix(prefix="evidence_", limit=limit, cursor=cursor)
        filtered = [
            row
            for row in rows
            if str(row.get("tenant_id") or "").strip()
            and normalize_storage_tenant_id(str(row.get("tenant_id"))) == tenant
        ]
        records: list[EvidenceRecord] = []
        for row in filtered:
            if "evidence_schema_version" not in row:
                legacy = EvidenceRecord.from_row(row, allow_legacy_schema=True)
                records.append(replace(legacy, schema_version=2).normalized())
                continue
            records.append(EvidenceRecord.from_row(row))
        return tuple(records), next_cursor


class LegacyDistributedEvidenceMigrationPort(Protocol):
    def read_prefix_batch(
        self,
        *,
        prefix: str,
        after_sequence_id: int = 0,
        limit: int = 500,
    ) -> tuple[Sequence[Mapping[str, Any]], int | None]: ...


def migrate_legacy_distributed_evidence(
    *,
    source: LegacyDistributedEvidenceMigrationPort,
    target: EvidenceStore,
    batch_size: int = 500,
) -> int:
    """Copy historical distributed Evidence rows into the canonical store.

    The legacy rows are intentionally retained as a rollback/archive surface.
    Active writers must use ``target`` after this migration completes. Rows are
    scanned in bounded sequence batches so startup migration cannot truncate or
    load the complete historical evidence set into memory.
    """
    migrated = 0
    cursor = 0
    while True:
        rows, next_cursor = source.read_prefix_batch(
            prefix="evidence_",
            after_sequence_id=cursor,
            limit=max(1, int(batch_size)),
        )
        if not rows:
            return migrated
        for raw in rows:
            row = dict(raw)
            schema_version = int(row.get("evidence_schema_version") or 1)
            if schema_version < EVIDENCE_SCHEMA_VERSION:
                legacy = EvidenceRecord.from_row(row, allow_legacy_schema=True)
                record = replace(legacy, schema_version=EVIDENCE_SCHEMA_VERSION).normalized_for_write()
            else:
                record = EvidenceRecord.from_row(row).normalized_for_write()
            existing = target.get(tenant_id=record.tenant_id, evidence_id=record.evidence_id)
            if existing is not None:
                if existing != record:
                    raise ValueError("legacy distributed evidence conflicts with canonical evidence")
                continue
            target.append(record)
            migrated += 1
        if next_cursor is None:
            return migrated
        if int(next_cursor) <= cursor:
            raise RuntimeError("legacy distributed evidence migration cursor did not advance")
        cursor = int(next_cursor)


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
    "LegacyDistributedEvidenceMigrationPort",
    "migrate_legacy_distributed_evidence",
]
