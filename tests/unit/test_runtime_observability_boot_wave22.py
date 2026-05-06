from __future__ import annotations

from boot.observability_boot import build_observability_surface, load_observability
from boot.runtime_boot import build_runtime_boot_surface
from observability.action_audit_log import FileActionAuditLog
from observability.decision_audit_log import FileDecisionAuditLog


def test_boot_observability_surface_uses_file_backed_audit_defaults(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BUSINESAIOS_DATA_DIR", str(tmp_path))
    surface = build_observability_surface()
    assert isinstance(surface.components["action_audit_log"], FileActionAuditLog)
    assert isinstance(surface.components["decision_audit_log"], FileDecisionAuditLog)
    payload = surface.payload()
    assert payload["action_audit_log"] is surface.components["action_audit_log"]
    assert payload["decision_audit_log"] is surface.components["decision_audit_log"]


def test_runtime_boot_reuses_canonical_observability_surface(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BUSINESAIOS_DATA_DIR", str(tmp_path))
    surface = build_runtime_boot_surface()
    snapshot = surface.observability_snapshot()
    assert snapshot["action_audit_log"] == "FileActionAuditLog"
    assert snapshot["decision_audit_log"] == "FileDecisionAuditLog"


def test_load_observability_payload_is_complete(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BUSINESAIOS_DATA_DIR", str(tmp_path))
    payload = load_observability()
    assert "event_bus" in payload
    assert "metrics" in payload
    assert "tracer" in payload
    assert "tenant_metrics_registry" in payload
    assert "audit_export_service" in payload
    assert "decision_audit_log" in payload
    assert "action_audit_log" in payload


def test_runtime_boot_surface_reuses_explicit_bootstrap_config_surface(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BUSINESAIOS_DATA_DIR", str(tmp_path))
    from boot.bootstrap_config_surface import build_bootstrap_config_surface
    config_surface = build_bootstrap_config_surface()
    surface = build_runtime_boot_surface(config_surface=config_surface)

    assert surface.config_surface is config_surface
    assert surface.observability_snapshot()["config"] == config_surface.snapshot()
