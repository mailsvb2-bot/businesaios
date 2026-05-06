from __future__ import annotations

from boot.bootstrap_config_surface import build_bootstrap_config_surface
from observability.action_audit_log import build_default_action_audit_log
from observability.decision_audit_log import build_default_decision_audit_log


def test_bootstrap_config_surface_exposes_canonical_observability_paths(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BUSINESAIOS_DATA_DIR", str(tmp_path / "runtime"))
    config = build_bootstrap_config_surface()
    assert config.action_audit_log_path.parent == config.observability_data_dir
    assert config.decision_audit_log_path.parent == config.observability_data_dir
    assert config.incident_signal_store_path.parent == config.observability_data_dir
    assert config.observability_export_dir.parent == config.observability_data_dir


def test_default_audit_logs_follow_explicit_config_surface_paths(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BUSINESAIOS_DATA_DIR", str(tmp_path / "runtime"))
    config = build_bootstrap_config_surface()
    action_log = build_default_action_audit_log(config_surface=config)
    decision_log = build_default_decision_audit_log(config_surface=config)
    assert getattr(action_log, "path", None) == config.action_audit_log_path
    assert getattr(decision_log, "path", None) == config.decision_audit_log_path
