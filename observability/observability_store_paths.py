from __future__ import annotations

CANON_COMPAT_SHIM = True

from pathlib import Path
import os

from boot.bootstrap_config_surface import BootstrapConfigSurface
from runtime.service_names import RuntimeServiceName

CANON_OBSERVABILITY_STORE_PATHS = True


def _base_observability_dir(*, config_surface: BootstrapConfigSurface | None = None) -> Path:
    if config_surface is not None:
        return config_surface.observability_data_dir
    explicit = os.getenv("BUSINESAIOS_OBSERVABILITY_DATA_DIR", "").strip()
    if explicit:
        return Path(explicit)
    return Path(os.getenv("DATA_DIR", "data")) / RuntimeServiceName.OBSERVABILITY


def action_audit_path(*, config_surface: BootstrapConfigSurface | None = None) -> Path:
    if config_surface is not None:
        return config_surface.action_audit_log_path
    explicit = os.getenv("BUSINESAIOS_ACTION_AUDIT_LOG_PATH", "").strip()
    if explicit:
        return Path(explicit)
    return _base_observability_dir(config_surface=None) / "action_audit_log.json"


def decision_audit_path(*, config_surface: BootstrapConfigSurface | None = None) -> Path:
    if config_surface is not None:
        return config_surface.decision_audit_log_path
    explicit = os.getenv("BUSINESAIOS_DECISION_AUDIT_LOG_PATH", "").strip()
    if explicit:
        return Path(explicit)
    return _base_observability_dir(config_surface=None) / "decision_audit_log.json"


def execution_trace_path(*, config_surface: BootstrapConfigSurface | None = None) -> Path:
    if config_surface is not None:
        return config_surface.execution_trace_store_path
    explicit = os.getenv("BUSINESAIOS_EXECUTION_TRACE_STORE_PATH", "").strip()
    if explicit:
        return Path(explicit)
    return _base_observability_dir(config_surface=None) / "execution_trace.jsonl"


def decision_trace_path(*, config_surface: BootstrapConfigSurface | None = None) -> Path:
    if config_surface is not None:
        return config_surface.decision_trace_store_path
    explicit = os.getenv("BUSINESAIOS_DECISION_TRACE_STORE_PATH", "").strip()
    if explicit:
        return Path(explicit)
    return _base_observability_dir(config_surface=None) / "decision_trace.jsonl"


def runtime_effect_trace_path(*, config_surface: BootstrapConfigSurface | None = None) -> Path:
    if config_surface is not None:
        return config_surface.runtime_effect_trace_store_path
    explicit = os.getenv("BUSINESAIOS_RUNTIME_EFFECT_TRACE_STORE_PATH", "").strip()
    if explicit:
        return Path(explicit)
    return _base_observability_dir(config_surface=None) / "runtime_effect_trace.jsonl"


def incident_signal_path(*, config_surface: BootstrapConfigSurface | None = None) -> Path:
    if config_surface is not None:
        return config_surface.incident_signal_store_path
    explicit = os.getenv("BUSINESAIOS_INCIDENT_SIGNAL_STORE_PATH", "").strip()
    if explicit:
        return Path(explicit)
    return _base_observability_dir(config_surface=None) / "incident_signals.json"


def telemetry_event_store_path(*, config_surface: BootstrapConfigSurface | None = None) -> Path:
    if config_surface is not None:
        return config_surface.telemetry_event_store_path
    explicit = os.getenv("BUSINESAIOS_TELEMETRY_EVENT_STORE_PATH", "").strip()
    if explicit:
        return Path(explicit)
    return _base_observability_dir(config_surface=None) / "telemetry_events.sqlite3"


def observability_export_dir(*, config_surface: BootstrapConfigSurface | None = None) -> Path:
    if config_surface is not None:
        return config_surface.observability_export_dir
    explicit = os.getenv("BUSINESAIOS_OBSERVABILITY_EXPORT_DIR", "").strip()
    if explicit:
        return Path(explicit)
    return _base_observability_dir(config_surface=None) / "exports"


def observability_export_catalog_path(*, config_surface: BootstrapConfigSurface | None = None) -> Path:
    if config_surface is not None:
        return config_surface.observability_export_catalog_path
    explicit = os.getenv("BUSINESAIOS_OBSERVABILITY_EXPORT_CATALOG_PATH", "").strip()
    if explicit:
        return Path(explicit)
    return observability_export_dir(config_surface=None) / "bundle_catalog.json"


__all__ = [
    "CANON_OBSERVABILITY_STORE_PATHS",
    "action_audit_path",
    "decision_audit_path",
    "execution_trace_path",
    "decision_trace_path",
    "runtime_effect_trace_path",
    "incident_signal_path",
    "telemetry_event_store_path",
    "observability_export_dir",
    "observability_export_catalog_path",
]
