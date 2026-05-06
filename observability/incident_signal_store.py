from __future__ import annotations

CANON_COMPAT_SHIM = True

from runtime.service_names import RuntimeServiceName

import os
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from boot.bootstrap_config_surface import BootstrapConfigSurface
from core.tenancy.normalization import require_tenant_id
from governance.persistence_codec import atomic_write_json, read_json_or_default, to_jsonable
from observability.audit_storage_policy import AuditStoragePolicy, build_default_audit_storage_policy, rotate_audit_file, serialize_records_payload, audit_segment_paths
from observability.storage_coordination import advisory_file_lock
from observability.observability_store_paths import incident_signal_path


CANON_INCIDENT_SIGNAL_STORE = True


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class IncidentStatus(str, Enum):
    OPEN = 'open'
    ACKNOWLEDGED = 'acknowledged'
    RESOLVED = 'resolved'


@dataclass(frozen=True)
class IncidentSignalRecord:
    incident_id: str
    tenant_id: str
    signal_type: str
    status: IncidentStatus = IncidentStatus.OPEN
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    severity: str = 'warning'
    trace_id: str | None = None
    rule_id: str | None = None
    dedup_key: str | None = None
    summary: str = ''
    payload: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not str(self.incident_id or '').strip():
            raise ValueError('incident_id is required')
        require_tenant_id(self.tenant_id)
        if not str(self.signal_type or '').strip():
            raise ValueError('signal_type is required')
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError('incident timestamps must be timezone-aware')



def incident_signal_store_path(*, config_surface=None) -> Path:
    return incident_signal_path(config_surface=config_surface)


class InMemoryIncidentSignalStore:
    def __init__(self) -> None:
        self._records: dict[str, IncidentSignalRecord] = {}

    def append(self, record: IncidentSignalRecord) -> IncidentSignalRecord:
        record.validate()
        self._records[record.incident_id] = record
        return record

    def upsert_open_by_dedup_key(self, record: IncidentSignalRecord) -> IncidentSignalRecord:
        record.validate()
        if record.dedup_key:
            for existing in self._records.values():
                if existing.tenant_id == record.tenant_id and existing.dedup_key == record.dedup_key and existing.status is not IncidentStatus.RESOLVED:
                    updated = replace(existing, updated_at=utc_now(), summary=record.summary or existing.summary, payload=dict(record.payload or existing.payload), severity=str(record.severity or existing.severity))
                    self._records[existing.incident_id] = updated
                    return updated
        self._records[record.incident_id] = record
        return record

    def get(self, *, tenant_id: str, incident_id: str) -> IncidentSignalRecord | None:
        tid = require_tenant_id(tenant_id)
        item = self._records.get(str(incident_id))
        if item is None or item.tenant_id != tid:
            return None
        return item

    def list_open(self, *, tenant_id: str) -> tuple[IncidentSignalRecord, ...]:
        tid = require_tenant_id(tenant_id)
        items = [item for item in self._records.values() if item.tenant_id == tid and item.status is not IncidentStatus.RESOLVED]
        items.sort(key=lambda x: x.created_at)
        return tuple(items)

    def acknowledge(self, *, tenant_id: str, incident_id: str) -> IncidentSignalRecord:
        record = self._require(tenant_id=tenant_id, incident_id=incident_id)
        updated = replace(record, status=IncidentStatus.ACKNOWLEDGED, updated_at=utc_now())
        self._records[incident_id] = updated
        return updated

    def resolve(self, *, tenant_id: str, incident_id: str) -> IncidentSignalRecord:
        record = self._require(tenant_id=tenant_id, incident_id=incident_id)
        updated = replace(record, status=IncidentStatus.RESOLVED, updated_at=utc_now())
        self._records[incident_id] = updated
        return updated

    def _require(self, *, tenant_id: str, incident_id: str) -> IncidentSignalRecord:
        record = self.get(tenant_id=tenant_id, incident_id=incident_id)
        if record is None:
            raise ValueError(f'incident not found: {incident_id}')
        return record


class PersistentIncidentSignalStore(InMemoryIncidentSignalStore):
    def __init__(self, path: str | Path | None = None, *, storage_policy: AuditStoragePolicy | None = None, config_surface: BootstrapConfigSurface | None = None) -> None:
        super().__init__()
        self._path = Path(path) if path is not None else incident_signal_store_path(config_surface=config_surface)
        self._storage_policy = storage_policy or build_default_audit_storage_policy(config_surface=config_surface)
        self._load()

    @property
    def path(self) -> Path:
        return self._path

    @property
    def storage_policy(self) -> AuditStoragePolicy:
        return self._storage_policy

    def append(self, record: IncidentSignalRecord) -> IncidentSignalRecord:
        with advisory_file_lock(self._path, exclusive=True):
            self._load()
            saved = super().append(record)
            self._flush()
            return saved

    def upsert_open_by_dedup_key(self, record: IncidentSignalRecord) -> IncidentSignalRecord:
        with advisory_file_lock(self._path, exclusive=True):
            self._load()
            saved = super().upsert_open_by_dedup_key(record)
            self._flush()
            return saved

    def acknowledge(self, *, tenant_id: str, incident_id: str) -> IncidentSignalRecord:
        with advisory_file_lock(self._path, exclusive=True):
            self._load()
            saved = super().acknowledge(tenant_id=tenant_id, incident_id=incident_id)
            self._flush()
            return saved

    def resolve(self, *, tenant_id: str, incident_id: str) -> IncidentSignalRecord:
        with advisory_file_lock(self._path, exclusive=True):
            self._load()
            saved = super().resolve(tenant_id=tenant_id, incident_id=incident_id)
            self._flush()
            return saved


    def get(self, *, tenant_id: str, incident_id: str) -> IncidentSignalRecord | None:
        with advisory_file_lock(self._path, exclusive=False):
            self._load()
            return super().get(tenant_id=tenant_id, incident_id=incident_id)

    def list_open(self, *, tenant_id: str) -> tuple[IncidentSignalRecord, ...]:
        with advisory_file_lock(self._path, exclusive=False):
            self._load()
            return super().list_open(tenant_id=tenant_id)

    def export_snapshot(self) -> dict[str, object]:
        with advisory_file_lock(self._path, exclusive=False):
            segments = audit_segment_paths(path=self._path, backup_count=self._storage_policy.backup_count)
        return {
            'path': str(self._path),
            'segment_count': len(segments),
            'segments': tuple(str(item) for item in segments),
        }

    def _load(self) -> None:
        raw = read_json_or_default(self._path, default={'records': []})
        records = raw.get('records', []) if isinstance(raw, dict) else []
        loaded: dict[str, IncidentSignalRecord] = {}
        for item in records:
            record = IncidentSignalRecord(
                incident_id=str(item['incident_id']),
                tenant_id=str(item['tenant_id']),
                signal_type=str(item['signal_type']),
                status=IncidentStatus(str(item.get('status', IncidentStatus.OPEN.value))),
                created_at=datetime.fromisoformat(str(item['created_at'])),
                updated_at=datetime.fromisoformat(str(item['updated_at'])),
                severity=str(item.get('severity', 'warning')),
                trace_id=item.get('trace_id'),
                rule_id=item.get('rule_id'),
                dedup_key=item.get('dedup_key'),
                summary=str(item.get('summary', '')),
                payload=dict(item.get('payload', {})),
            )
            loaded[record.incident_id] = record
        self._records = loaded

    def _flush(self) -> None:
        records = [{str(k): to_jsonable(v) for k, v in asdict(item).items()} for item in self._records.values()]
        payload = {'records': self._storage_policy.compact_records(records)}
        serialized = serialize_records_payload(records=payload['records'])
        if self._storage_policy.should_rotate(path=self._path, serialized_payload=serialized):
            rotate_audit_file(path=self._path, backup_count=self._storage_policy.backup_count)
        atomic_write_json(self._path, payload)


__all__ = [
    'CANON_INCIDENT_SIGNAL_STORE',
    'InMemoryIncidentSignalStore',
    'IncidentSignalRecord',
    'IncidentStatus',
    'PersistentIncidentSignalStore',
    'incident_signal_store_path',
    'utc_now',
]
