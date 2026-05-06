from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Protocol

from observability.audit_export_service import AuditExportService
from runtime.business_autonomy.distributed_state import FileDistributedEvidenceAppendPort

CANON_PROVIDER_RUNTIME_EXPORT_BRIDGE = True


def _runtime_root() -> Path:
    from application.business_autonomy.persistence import business_autonomy_runtime_dir
    return business_autonomy_runtime_dir() / 'distributed' / 'provider_exports'


class ProviderRuntimeExportLedger(Protocol):
    def append(self, row: Mapping[str, Any]) -> dict[str, Any]: ...
    def list_for_provider(self, *, tenant_id: str, business_id: str, provider_key: str, limit: int = 50) -> tuple[dict[str, Any], ...]: ...


@dataclass
class InMemoryProviderRuntimeExportHistory:
    rows: list[dict[str, Any]] = field(default_factory=list)

    def append(self, row: Mapping[str, Any]) -> dict[str, Any]:
        item = dict(row)
        self.rows.append(item)
        return item

    def list_for_provider(self, *, tenant_id: str, business_id: str, provider_key: str, limit: int = 50) -> tuple[dict[str, Any], ...]:
        rows = [dict(item) for item in self.rows if str(item.get('tenant_id')) == str(tenant_id) and str(item.get('business_id')) == str(business_id) and str(item.get('provider_key')) == str(provider_key)]
        rows.sort(key=lambda row: str(row.get('event_kind') or '') + str(row.get('bundle_name') or ''), reverse=True)
        return tuple(rows[: max(1, int(limit))])


@dataclass(frozen=True)
class FileProviderRuntimeExportLedger:
    append_port: FileDistributedEvidenceAppendPort
    partition_prefix: str = 'provider_runtime_exports'

    @classmethod
    def default(cls) -> 'FileProviderRuntimeExportLedger':
        return cls(FileDistributedEvidenceAppendPort(_runtime_root() / 'append'))

    def append(self, row: Mapping[str, Any]) -> dict[str, Any]:
        payload = dict(row)
        partition_key = f"{self.partition_prefix}/{payload.get('tenant_id')}/{payload.get('business_id')}/{payload.get('provider_key')}"
        export_id = self.append_port.append(partition_key=partition_key, payload=payload)
        return {**payload, 'export_id': export_id}

    def list_for_provider(self, *, tenant_id: str, business_id: str, provider_key: str, limit: int = 50) -> tuple[dict[str, Any], ...]:
        rows, _ = self.append_port.read_partition(partition_key=f"{self.partition_prefix}/{tenant_id}/{business_id}/{provider_key}", limit=limit)
        return tuple(dict(item) for item in rows)


@dataclass(frozen=True)
class ProviderRuntimeExportBridge:
    export_service: AuditExportService = field(default_factory=AuditExportService)
    history: ProviderRuntimeExportLedger = field(default_factory=FileProviderRuntimeExportLedger.default)

    def export_runtime_event(self, *, tenant_id: str, business_id: str, provider_key: str, event_kind: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        bundle_name = f'provider-{event_kind}-{tenant_id}-{business_id}-{provider_key}'
        record = {'tenant_id': str(tenant_id), 'business_id': str(business_id), 'provider_key': str(provider_key), 'event_kind': str(event_kind), 'payload': dict(payload)}
        bundle = self.export_service.export_json(bundle_name=bundle_name, records=[record])
        history_row = self.history.append({'tenant_id': str(tenant_id), 'business_id': str(business_id), 'provider_key': str(provider_key), 'event_kind': str(event_kind), 'bundle_name': bundle_name, 'record': record})
        return {'bundle_name': bundle_name, 'bundle_preview': bundle[:800], 'history_row': history_row}

    def list_history(self, *, tenant_id: str, business_id: str, provider_key: str, limit: int = 50) -> tuple[dict[str, Any], ...]:
        return self.history.list_for_provider(tenant_id=tenant_id, business_id=business_id, provider_key=provider_key, limit=limit)


__all__ = ['CANON_PROVIDER_RUNTIME_EXPORT_BRIDGE', 'ProviderRuntimeExportBridge', 'InMemoryProviderRuntimeExportHistory', 'FileProviderRuntimeExportLedger']
