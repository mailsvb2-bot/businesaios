from __future__ import annotations

import json
from pathlib import Path

from boot.bootstrap_config_surface import BootstrapConfigSurface
from observability.audit_export_service import AuditExportService


def _config(tmp_path: Path) -> BootstrapConfigSurface:
    obs = tmp_path / 'obs'
    return BootstrapConfigSurface(
        data_dir=tmp_path / 'data',
        observability_data_dir=obs,
        observability_store_mode='file',
        action_audit_backend='file',
        decision_audit_backend='file',
        api_idempotency_path=tmp_path / 'api' / 'idempotency.sqlite3',
        action_audit_log_path=obs / 'action_audit_log.json',
        decision_audit_log_path=obs / 'decision_audit_log.json',
        execution_trace_store_path=obs / 'execution_trace.jsonl',
        decision_trace_store_path=obs / 'decision_trace.jsonl',
        runtime_effect_trace_store_path=obs / 'runtime_effect_trace.jsonl',
        incident_signal_store_path=obs / 'incident_signals.json',
        telemetry_event_store_path=obs / 'telemetry.sqlite3',
        telemetry_event_store_backend='sqlite',
        observability_export_dir=obs / 'exports',
        observability_export_catalog_path=obs / 'exports' / 'bundle_catalog.json',
        observability_export_retention_count=10,
        audit_max_records=100,
        audit_max_bytes=100000,
        audit_backup_count=1,
        trace_max_records=100,
        trace_max_bytes=100000,
        trace_backup_count=1,
    )


def test_read_bundle_rejects_identity_mismatch(tmp_path: Path) -> None:
    service = AuditExportService(config_surface=_config(tmp_path))
    path = service.write_compliance_bundle(
        bundle_name='tenant-a-bundle',
        tenant_id='tenant-a',
        audit_events=[],
        incidents=[],
    )
    payload = json.loads(path.read_text(encoding='utf-8'))
    payload['bundle_identity'] = {'bundle_kind': 'compliance', 'bundle_name': 'tampered'}
    path.write_text(json.dumps(payload), encoding='utf-8')
    try:
        service.read_bundle(bundle_kind='compliance', bundle_name='tenant-a-bundle')
    except ValueError as exc:
        assert 'bundle identity mismatch' in str(exc)
    else:
        raise AssertionError('expected bundle identity mismatch')
