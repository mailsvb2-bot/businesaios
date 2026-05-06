from __future__ import annotations

import pytest

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


def test_restore_latest_bundle_round_trips_latest_registered_payload(tmp_path) -> None:
    config = _config(tmp_path)
    service = AuditExportService(config_surface=config)
    service.write_compliance_bundle(bundle_name="tenant-a-old", tenant_id="tenant-a", audit_events=(), incidents=())
    service.write_compliance_bundle(bundle_name="tenant-a-new", tenant_id="tenant-a", audit_events=(), incidents=())

    payload = service.restore_latest_bundle(bundle_kind="compliance", expected_tenant_id="tenant-a")

    assert payload["tenant_id"] == "tenant-a"
    assert payload["metadata"]["audit_event_count"] == 0


def test_restore_bundle_fails_closed_on_tenant_mismatch(tmp_path) -> None:
    config = _config(tmp_path)
    service = AuditExportService(config_surface=config)
    service.write_recovery_bundle(
        bundle_name="tenant-a-recovery",
        tenant_id="tenant-a",
        recovery_plan={"plan": "resume"},
        transport_results=(),
        incidents=(),
    )

    with pytest.raises(ValueError, match="bundle tenant mismatch"):
        service.restore_bundle(bundle_kind="recovery", bundle_name="tenant-a-recovery", expected_tenant_id="tenant-b")
