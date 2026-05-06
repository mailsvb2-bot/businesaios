from __future__ import annotations

CANON_COMPAT_SHIM = True

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Any

from boot.bootstrap_config_surface import BootstrapConfigSurface, build_bootstrap_config_surface
from observability.observability_store_paths import observability_export_catalog_path, observability_export_dir
from governance.persistence_codec import atomic_write_json, ensure_parent_dir, to_jsonable, read_json_or_default
from observability.storage_coordination import advisory_file_lock
from observability.export_bundle_catalog import ExportBundleCatalog, ExportBundleEntry
from observability.audit_event_schema import AuditEventRecord
from observability.execution_trace_contract import DecisionTraceEvent, ExecutionTraceEvent, RuntimeEffectTraceEvent
from observability.incident_signal_store import IncidentSignalRecord
from observability.observability_bundle_policy import build_observability_bundle_metadata, build_record_bundle_metadata, payload_sha256
from observability.observability_export_manifest import build_observability_export_manifest


CANON_AUDIT_EXPORT_SERVICE = True


class AuditExportService:
    """Export-only service.

    Serializes already-existing evidence.
    It does not create policy, incidents, or decisions.
    """

    def __init__(self, *, config_surface: BootstrapConfigSurface | None = None) -> None:
        self._config_surface = config_surface or build_bootstrap_config_surface()
        self._catalog = ExportBundleCatalog(observability_export_catalog_path(config_surface=self._config_surface))

    @property
    def config_surface(self) -> BootstrapConfigSurface:
        return self._config_surface

    @property
    def bundle_catalog(self) -> ExportBundleCatalog:
        return self._catalog

    def export_ndjson(self, records: Iterable[object]) -> str:
        return "\n".join(
            json.dumps(self._serialize_record(item), ensure_ascii=False, sort_keys=True)
            for item in records
        )

    def export_json(self, *, bundle_name: str, records: Iterable[object]) -> str:
        payload = {
            'bundle_name': str(bundle_name),
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'records': [self._serialize_record(item) for item in records],
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)

    def export_trace_bundle(
        self,
        *,
        trace_id: str,
        execution_events: Iterable[ExecutionTraceEvent],
        decision_events: Iterable[DecisionTraceEvent],
        effect_events: Iterable[RuntimeEffectTraceEvent],
        audit_events: Iterable[AuditEventRecord] = (),
        incident_events: Iterable[IncidentSignalRecord] = (),
    ) -> dict[str, object]:
        return {
            'trace_id': str(trace_id),
            'execution_events': [self._serialize_record(item) for item in execution_events],
            'decision_events': [self._serialize_record(item) for item in decision_events],
            'effect_events': [self._serialize_record(item) for item in effect_events],
            'audit_events': [self._serialize_record(item) for item in audit_events],
            'incident_events': [self._serialize_record(item) for item in incident_events],
        }

    def export_observability_bundle(self, *, stores: Mapping[str, object]) -> dict[str, object]:
        manifest = build_observability_export_manifest(stores=dict(stores))
        return {
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'stores': manifest,
            'metadata': build_observability_bundle_metadata(stores=manifest),
        }

    def export_compliance_bundle(
        self,
        *,
        tenant_id: str,
        audit_events: Iterable[AuditEventRecord],
        incidents: Iterable[IncidentSignalRecord],
    ) -> dict[str, object]:
        serialized_audit = [self._serialize_record(item) for item in audit_events]
        serialized_incidents = [self._serialize_record(item) for item in incidents]
        return {
            'tenant_id': str(tenant_id),
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'audit_events': serialized_audit,
            'incidents': serialized_incidents,
            'metadata': {
                'generated_at': datetime.now(timezone.utc).isoformat(),
                **build_record_bundle_metadata(records={
                    'tenant_id': tenant_id,
                    'audit_events': serialized_audit,
                    'incidents': serialized_incidents,
                }),
                'audit_event_count': len(serialized_audit),
                'incident_count': len(serialized_incidents),
            },
        }

    def export_recovery_bundle(
        self,
        *,
        tenant_id: str,
        recovery_plan: Mapping[str, object],
        transport_results: Iterable[Mapping[str, object]],
        incidents: Iterable[IncidentSignalRecord] = (),
    ) -> dict[str, object]:
        transport_items = [dict(self._serialize_record(item)) for item in transport_results]
        incident_items = [self._serialize_record(item) for item in incidents]
        payload = {
            'tenant_id': str(tenant_id),
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'recovery_plan': dict(self._serialize_record(recovery_plan)),
            'transport_results': transport_items,
            'incidents': incident_items,
        }
        payload['metadata'] = {
            'transport_result_count': len(transport_items),
            'incident_count': len(incident_items),
            'payload_sha256': payload_sha256(payload),
        }
        return payload

    def write_observability_bundle(self, *, bundle_name: str, stores: Mapping[str, object]) -> Path:
        payload = self.export_observability_bundle(stores=stores)
        return self._write_bundle(bundle_kind='observability', bundle_name=bundle_name, payload=payload)

    def write_compliance_bundle(
        self,
        *,
        bundle_name: str,
        tenant_id: str,
        audit_events: Iterable[AuditEventRecord],
        incidents: Iterable[IncidentSignalRecord],
    ) -> Path:
        payload = self.export_compliance_bundle(tenant_id=tenant_id, audit_events=audit_events, incidents=incidents)
        return self._write_bundle(bundle_kind='compliance', bundle_name=bundle_name, payload=payload)

    def write_recovery_bundle(
        self,
        *,
        bundle_name: str,
        tenant_id: str,
        recovery_plan: Mapping[str, object],
        transport_results: Iterable[Mapping[str, object]],
        incidents: Iterable[IncidentSignalRecord] = (),
    ) -> Path:
        payload = self.export_recovery_bundle(
            tenant_id=tenant_id,
            recovery_plan=recovery_plan,
            transport_results=transport_results,
            incidents=incidents,
        )
        return self._write_bundle(bundle_kind='recovery', bundle_name=bundle_name, payload=payload)

    def restore_bundle(self, *, bundle_kind: str, bundle_name: str, expected_tenant_id: str | None = None) -> dict[str, object]:
        payload = self.read_bundle(bundle_kind=bundle_kind, bundle_name=bundle_name)
        tenant_id = payload.get('tenant_id')
        if expected_tenant_id is not None and tenant_id is not None and str(tenant_id) != str(expected_tenant_id):
            raise ValueError(f'bundle tenant mismatch: expected {expected_tenant_id}, got {tenant_id}')
        return payload

    def restore_latest_bundle(self, *, bundle_kind: str, expected_tenant_id: str | None = None) -> dict[str, object]:
        entry = self.bundle_catalog.latest(bundle_kind=bundle_kind)
        if entry is None:
            raise FileNotFoundError(f'no bundle registered for kind: {bundle_kind}')
        return self.restore_bundle(
            bundle_kind=bundle_kind,
            bundle_name=entry.bundle_name,
            expected_tenant_id=expected_tenant_id,
        )

    def _write_bundle(self, *, bundle_kind: str, bundle_name: str, payload: Mapping[str, object]) -> Path:
        safe_name = ''.join(ch if ch.isalnum() or ch in {'-', '_'} else '-' for ch in str(bundle_name)).strip('-') or 'bundle'
        export_dir = ensure_parent_dir(observability_export_dir(config_surface=self.config_surface) / bundle_kind / f'{safe_name}.json').parent
        path = export_dir / f'{safe_name}.json'
        stamped_payload = dict(payload)
        stamped_payload['bundle_identity'] = {
            'bundle_kind': str(bundle_kind),
            'bundle_name': safe_name,
        }
        with advisory_file_lock(path, exclusive=True):
            atomic_write_json(path, stamped_payload)
        self._catalog.register(bundle_kind=bundle_kind, bundle_name=safe_name, path=path, payload=stamped_payload)
        self._prune_bundle_history(bundle_kind=bundle_kind)
        self.verify_bundle(bundle_kind=bundle_kind, bundle_name=safe_name)
        return path

    def _prune_bundle_history(self, *, bundle_kind: str) -> None:
        removed = self.bundle_catalog.prune(
            bundle_kind=bundle_kind,
            keep_latest=self.config_surface.observability_export_retention_count,
        )
        for entry in removed:
            path = Path(entry.path)
            try:
                path.unlink()
            except FileNotFoundError:
                continue

    def enforce_retention(self, *, bundle_kind: str | None = None) -> dict[str, object]:
        removed_entries: list[ExportBundleEntry] = []
        kinds = (bundle_kind,) if bundle_kind is not None else self.bundle_catalog.bundle_kinds()
        for kind in kinds:
            removed_entries.extend(self.bundle_catalog.prune(
                bundle_kind=kind,
                keep_latest=self.config_surface.observability_export_retention_count,
            ))
        removed_names: list[str] = []
        for entry in removed_entries:
            removed_names.append(entry.bundle_name)
            try:
                Path(entry.path).unlink()
            except FileNotFoundError:
                continue
        return {
            'bundle_kind': bundle_kind,
            'removed_count': len(removed_entries),
            'removed_bundle_names': tuple(removed_names),
        }

    def repair_catalog(self, *, bundle_kind: str | None = None) -> dict[str, object]:
        removed = self.bundle_catalog.prune_missing(bundle_kind=bundle_kind)
        return {
            'bundle_kind': bundle_kind,
            'removed_count': len(removed),
            'removed_bundle_names': tuple(entry.bundle_name for entry in removed),
        }

    def verify_bundle(self, *, bundle_kind: str, bundle_name: str) -> dict[str, object]:
        payload = self.read_bundle(bundle_kind=bundle_kind, bundle_name=bundle_name)
        entry = self.bundle_catalog.get(bundle_kind=bundle_kind, bundle_name=bundle_name)
        return {
            'bundle_kind': bundle_kind,
            'bundle_name': bundle_name,
            'path': entry.path if entry is not None else None,
            'payload_sha256': build_record_bundle_metadata(records=payload).get('payload_sha256'),
            'verified': True,
        }

    def verify_catalog(self, *, bundle_kind: str | None = None) -> dict[str, object]:
        self.repair_catalog(bundle_kind=bundle_kind)
        entries = self.bundle_catalog.list_entries(bundle_kind=bundle_kind)
        results: list[dict[str, object]] = []
        for entry in entries:
            try:
                verification = self.verify_bundle(bundle_kind=entry.bundle_kind, bundle_name=entry.bundle_name)
            except Exception as exc:  # pragma: no cover - surfaced in verification report
                verification = {
                    'bundle_kind': entry.bundle_kind,
                    'bundle_name': entry.bundle_name,
                    'path': entry.path,
                    'payload_sha256': entry.payload_sha256,
                    'verified': False,
                    'error': str(exc),
                }
            results.append(verification)
        verified_count = sum(1 for item in results if item.get('verified') is True)
        return {
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'bundle_count': len(results),
            'verified_count': verified_count,
            'failed_count': len(results) - verified_count,
            'entries': results,
            'catalog_sha256': payload_sha256({
                'entries': results,
                'bundle_count': len(results),
                'verified_count': verified_count,
            }),
        }

    def read_bundle(self, *, bundle_kind: str, bundle_name: str) -> dict[str, object]:
        entry = self._catalog.get(bundle_kind=bundle_kind, bundle_name=str(bundle_name))
        if entry is None:
            raise FileNotFoundError(f'bundle not registered: {bundle_kind}/{bundle_name}')
        path = Path(entry.path)
        with advisory_file_lock(path, exclusive=False):
            payload = read_json_or_default(path, default={})
        if not isinstance(payload, dict):
            raise ValueError(f'bundle payload must be a mapping: {path}')
        identity = payload.get('bundle_identity') if isinstance(payload.get('bundle_identity'), dict) else {}
        if str(identity.get('bundle_kind') or '') != str(bundle_kind) or str(identity.get('bundle_name') or '') != str(bundle_name):
            raise ValueError(f'bundle identity mismatch: {path}')
        actual_sha = build_record_bundle_metadata(records=payload).get('payload_sha256')
        if actual_sha != entry.payload_sha256:
            raise ValueError(f'bundle fingerprint mismatch: {path}')
        return dict(payload)

    @staticmethod
    def _serialize_record(item: object) -> Mapping[str, object]:
        if is_dataclass(item):
            return {str(k): to_jsonable(v) for k, v in asdict(item).items()}
        if isinstance(item, dict):
            return {str(k): to_jsonable(v) for k, v in item.items()}
        raise TypeError(f'unsupported export record type: {type(item)!r}')


__all__ = [
    'AuditExportService',
    'CANON_AUDIT_EXPORT_SERVICE',
]
