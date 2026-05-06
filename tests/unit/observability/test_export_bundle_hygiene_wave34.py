from pathlib import Path

from boot.bootstrap_config_surface import BootstrapConfigSurface
from observability.audit_export_service import AuditExportService


def _cfg(tmp_path: Path) -> BootstrapConfigSurface:
    root = tmp_path / 'runtime'
    obs = root / 'observability'
    return BootstrapConfigSurface(
        data_dir=root,
        observability_data_dir=obs,
        observability_store_mode='file',
        action_audit_backend='file',
        decision_audit_backend='file',
        api_idempotency_path=root / 'api' / 'idempotency.sqlite3',
        action_audit_log_path=obs / 'action_audit_log.json',
        decision_audit_log_path=obs / 'decision_audit_log.json',
        execution_trace_store_path=obs / 'execution_trace.jsonl',
        decision_trace_store_path=obs / 'decision_trace.jsonl',
        runtime_effect_trace_store_path=obs / 'runtime_effect_trace.jsonl',
        incident_signal_store_path=obs / 'incident_signals.json',
        observability_export_dir=obs / 'exports',
        observability_export_catalog_path=obs / 'exports' / 'bundle_catalog.json',
        observability_export_retention_count=2,
    )


def test_repair_catalog_prunes_missing_bundle_entries(tmp_path: Path) -> None:
    service = AuditExportService(config_surface=_cfg(tmp_path))
    path = service.write_compliance_bundle(bundle_name='tenant-a', tenant_id='tenant-a', audit_events=(), incidents=())
    path.unlink()
    report = service.repair_catalog(bundle_kind='compliance')
    assert report['removed_count'] == 1
    assert service.bundle_catalog.list_entries(bundle_kind='compliance') == ()


def test_enforce_retention_prunes_old_bundle_files_and_catalog(tmp_path: Path) -> None:
    service = AuditExportService(config_surface=_cfg(tmp_path))
    first = service.write_compliance_bundle(bundle_name='one', tenant_id='tenant-a', audit_events=(), incidents=())
    service.write_compliance_bundle(bundle_name='two', tenant_id='tenant-a', audit_events=(), incidents=())
    service.write_compliance_bundle(bundle_name='three', tenant_id='tenant-a', audit_events=(), incidents=())
    report = service.enforce_retention(bundle_kind='compliance')
    assert report['removed_count'] == 0
    assert [e.bundle_name for e in service.bundle_catalog.list_entries(bundle_kind='compliance')] == ['two', 'three']
    assert not first.exists()
