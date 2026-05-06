from __future__ import annotations

from boot.bootstrap_config_surface import BootstrapConfigSurface
from observability.action_audit_log import FileActionAuditLog
from observability.audit_export_service import AuditExportService
from observability.incident_signal_store import IncidentSignalRecord
from reliability.recovery_orchestrator import RecoveryPlan, TransportRecoveryResult


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


def test_write_observability_bundle_uses_configured_export_dir(tmp_path) -> None:
    config = _config(tmp_path)
    action_log = FileActionAuditLog(path=config.action_audit_log_path)
    action_log.record({"tenant_id": "tenant-a", "action_id": "a1", "action_type": "launch", "status": "ok"})
    service = AuditExportService(config_surface=config)
    path = service.write_observability_bundle(bundle_name="tenant a/primary", stores={"action": action_log})
    assert path.parent == config.observability_export_dir / "observability"
    assert path.exists()
    assert "tenant-a-primary" in path.name


def test_recovery_bundle_contains_metadata_and_can_be_written(tmp_path) -> None:
    config = _config(tmp_path)
    service = AuditExportService(config_surface=config)
    plan = RecoveryPlan(
        run_id="run-1",
        recovery_action="resume_delivery",
        reason="claimable_outbox",
        reconciliation={"anomalies": ()},
    )
    result = TransportRecoveryResult(
        transport_name="email", worker_id="worker-1", backend_name="smtp", processed=1, delivered=1, retried=0, dead_lettered=0, skipped=0
    )
    incident = IncidentSignalRecord(incident_id="i1", tenant_id="tenant-a", signal_type="recovery", summary="resume")
    bundle = service.export_recovery_bundle(tenant_id="tenant-a", recovery_plan=plan, transport_results=[result], incidents=[incident])
    assert bundle["metadata"]["transport_result_count"] == 1
    assert bundle["metadata"]["incident_count"] == 1
    assert len(bundle["metadata"]["payload_sha256"]) == 64
    path = service.write_recovery_bundle(bundle_name="recover-1", tenant_id="tenant-a", recovery_plan=plan, transport_results=[result], incidents=[incident])
    assert path.parent == config.observability_export_dir / "recovery"
    assert path.exists()
