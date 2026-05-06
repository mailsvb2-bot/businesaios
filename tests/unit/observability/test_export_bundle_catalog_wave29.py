from __future__ import annotations

import json

from boot.bootstrap_config_surface import BootstrapConfigSurface
from observability.audit_export_service import AuditExportService
from observability.action_audit_log import FileActionAuditLog


def _config(tmp_path) -> BootstrapConfigSurface:
    base = tmp_path / "runtime"
    obs = base / "observability"
    return BootstrapConfigSurface(
        data_dir=base,
        observability_data_dir=obs,
        observability_store_mode="file",
        action_audit_backend="file",
        decision_audit_backend="file",
        api_idempotency_path=base / "api" / "idempotency.sqlite3",
        action_audit_log_path=obs / "action_audit.json",
        decision_audit_log_path=obs / "decision_audit.json",
        execution_trace_store_path=obs / "execution_trace.jsonl",
        decision_trace_store_path=obs / "decision_trace.jsonl",
        runtime_effect_trace_store_path=obs / "runtime_effect_trace.jsonl",
        incident_signal_store_path=obs / "incident.json",
        observability_export_dir=obs / "exports",
        observability_export_catalog_path=obs / "exports" / "bundle_catalog.json",
    )


def test_bundle_write_registers_catalog_and_read_verifies_fingerprint(tmp_path) -> None:
    config = _config(tmp_path)
    action_log = FileActionAuditLog(path=config.action_audit_log_path)
    action_log.record({"tenant_id": "tenant-a", "action_id": "a1", "action_type": "launch", "status": "ok"})
    service = AuditExportService(config_surface=config)
    path = service.write_observability_bundle(bundle_name="tenant/a", stores={"action": action_log})
    assert path.exists()
    entry = service.bundle_catalog.get(bundle_kind="observability", bundle_name="tenant-a")
    assert entry is not None
    payload = service.read_bundle(bundle_kind="observability", bundle_name="tenant-a")
    assert payload["stores"]["action"]["path"] == str(config.action_audit_log_path)


def test_bundle_read_detects_fingerprint_mismatch(tmp_path) -> None:
    config = _config(tmp_path)
    service = AuditExportService(config_surface=config)
    path = service.write_compliance_bundle(bundle_name="tenant-a", tenant_id="tenant-a", audit_events=(), incidents=())
    payload = json.loads(path.read_text())
    payload["metadata"]["audit_event_count"] = 999
    path.write_text(json.dumps(payload))
    try:
        service.read_bundle(bundle_kind="compliance", bundle_name="tenant-a")
    except ValueError as exc:
        assert "fingerprint mismatch" in str(exc)
    else:
        raise AssertionError("expected fingerprint mismatch")
