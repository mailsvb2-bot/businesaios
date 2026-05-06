from boot.bootstrap_config_surface import BootstrapConfigSurface
from boot.observability_boot import build_observability_surface
from observability.audit_storage_policy import build_default_audit_storage_policy
from observability.trace_storage_policy import build_default_trace_storage_policy


def _cfg(tmp_path):
    obs = tmp_path / 'obs'
    exp = obs / 'exports'
    return BootstrapConfigSurface(
        data_dir=tmp_path / 'data',
        observability_data_dir=obs,
        observability_store_mode='persistent',
        action_audit_backend='file',
        decision_audit_backend='file',
        api_idempotency_path=tmp_path / 'api' / 'idempotency.sqlite3',
        action_audit_log_path=obs / 'action_audit.json',
        decision_audit_log_path=obs / 'decision_audit.json',
        execution_trace_store_path=obs / 'execution_trace.jsonl',
        decision_trace_store_path=obs / 'decision_trace.jsonl',
        runtime_effect_trace_store_path=obs / 'runtime_effect_trace.jsonl',
        incident_signal_store_path=obs / 'incident.json',
        observability_export_dir=exp,
        observability_export_catalog_path=exp / 'bundle_catalog.json',
        audit_max_records=7,
        audit_max_bytes=777,
        audit_backup_count=3,
        trace_max_records=9,
        trace_max_bytes=999,
        trace_backup_count=5,
    )


def test_storage_policies_follow_bootstrap_config_surface(tmp_path) -> None:
    cfg = _cfg(tmp_path)
    audit = build_default_audit_storage_policy(config_surface=cfg)
    trace = build_default_trace_storage_policy(config_surface=cfg)
    assert audit.max_records == 7
    assert audit.max_bytes == 777
    assert audit.backup_count == 3
    assert trace.max_records_per_segment == 9
    assert trace.max_bytes_per_segment == 999
    assert trace.backup_count == 5


def test_persistent_stores_use_configured_policies(tmp_path) -> None:
    cfg = _cfg(tmp_path)
    surface = build_observability_surface(config_surface=cfg)
    assert surface.components['action_audit_log'].storage_policy.max_records == 7
    assert surface.components['decision_audit_log'].storage_policy.backup_count == 3
    assert surface.components['execution_trace_store'].storage_policy.max_records_per_segment == 9
    assert surface.components['runtime_effect_trace_store'].storage_policy.backup_count == 5
