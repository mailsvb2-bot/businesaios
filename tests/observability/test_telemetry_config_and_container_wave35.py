from boot.bootstrap_config_surface import BootstrapConfigSurface
from boot.platform_boot_contract import build_validated_platform_boot_surface
from observability.platform.telemetry.event_store import JsonlEventStore, SqliteEventStore, build_default_event_store


def _config(tmp_path, backend: str = 'sqlite') -> BootstrapConfigSurface:
    observability_dir = tmp_path / 'observability'
    return BootstrapConfigSurface(
        data_dir=tmp_path,
        observability_data_dir=observability_dir,
        observability_store_mode='persistent',
        action_audit_backend='file',
        decision_audit_backend='file',
        api_idempotency_path=tmp_path / 'api' / 'idempotency.sqlite3',
        action_audit_log_path=observability_dir / 'action_audit_log.json',
        decision_audit_log_path=observability_dir / 'decision_audit_log.json',
        execution_trace_store_path=observability_dir / 'execution_trace.jsonl',
        decision_trace_store_path=observability_dir / 'decision_trace.jsonl',
        runtime_effect_trace_store_path=observability_dir / 'runtime_effect_trace.jsonl',
        incident_signal_store_path=observability_dir / 'incident_signals.json',
        telemetry_event_store_path=observability_dir / ('telemetry_events.jsonl' if backend == 'jsonl' else 'telemetry_events.sqlite3'),
        telemetry_event_store_backend=backend,
        observability_export_dir=observability_dir / 'exports',
        observability_export_catalog_path=observability_dir / 'exports' / 'bundle_catalog.json',
    )


def test_build_default_event_store_uses_configured_backend_and_path(tmp_path) -> None:
    sqlite_config = _config(tmp_path, backend='sqlite')
    sqlite_store = build_default_event_store(config_surface=sqlite_config)
    assert isinstance(sqlite_store, SqliteEventStore)
    assert sqlite_store.path == sqlite_config.telemetry_event_store_path

    jsonl_config = _config(tmp_path / 'jsonl', backend='jsonl')
    jsonl_store = build_default_event_store(config_surface=jsonl_config)
    assert isinstance(jsonl_store, JsonlEventStore)
    assert jsonl_store.path == jsonl_config.telemetry_event_store_path


def test_dependency_container_reuses_shared_telemetry_event_store(tmp_path) -> None:
    config_surface = _config(tmp_path, backend='sqlite')
    surface = build_validated_platform_boot_surface(config_surface=config_surface)
    runtime_store = surface.runtime_surface.orchestrator.services.get('telemetry_event_store')
    assert runtime_store is not None
    assert surface.dependency_container.telemetry_event_store() is runtime_store
