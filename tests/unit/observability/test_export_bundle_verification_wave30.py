from __future__ import annotations

import json

from boot.bootstrap_config_surface import BootstrapConfigSurface
from observability.audit_export_service import AuditExportService


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


def test_verify_catalog_reports_success_for_written_bundle(tmp_path) -> None:
    config = _config(tmp_path)
    service = AuditExportService(config_surface=config)
    service.write_compliance_bundle(bundle_name="tenant-a", tenant_id="tenant-a", audit_events=(), incidents=())
    report = service.verify_catalog(bundle_kind="compliance")
    assert report["bundle_count"] == 1
    assert report["verified_count"] == 1
    assert report["failed_count"] == 0
    assert len(report["catalog_sha256"]) == 64


def test_verify_catalog_reports_corruption_without_silent_success(tmp_path) -> None:
    config = _config(tmp_path)
    service = AuditExportService(config_surface=config)
    path = service.write_compliance_bundle(bundle_name="tenant-a", tenant_id="tenant-a", audit_events=(), incidents=())
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["metadata"]["audit_event_count"] = 42
    path.write_text(json.dumps(payload), encoding="utf-8")
    report = service.verify_catalog(bundle_kind="compliance")
    assert report["bundle_count"] == 1
    assert report["verified_count"] == 0
    assert report["failed_count"] == 1
    assert "fingerprint mismatch" in report["entries"][0]["error"]
