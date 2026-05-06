from __future__ import annotations

from pathlib import Path

from boot.bootstrap_config_surface import BootstrapConfigSurface
from observability.platform.telemetry.event_store import JsonlEventStore, build_default_event_store


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
        telemetry_event_store_path=obs / 'telemetry_events.jsonl',
        telemetry_event_store_backend='jsonl',
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


def test_jsonl_telemetry_store_uses_configured_path_and_locking(tmp_path: Path) -> None:
    config = _config(tmp_path)
    store = build_default_event_store(config_surface=config)
    assert isinstance(store, JsonlEventStore)
    assert store.path == config.telemetry_event_store_path
    store.append(tenant_id='tenant-a', user_id='user-1', event_type='event.created', payload={'x': 1})
    rows = list(store.iter_events(tenant_id='tenant-a'))
    assert len(rows) == 1
    assert rows[0]['event_type'] == 'event.created'
    lock_files = list(store.path.parent.glob(f'{store.path.name}.lock*'))
    assert lock_files == []
