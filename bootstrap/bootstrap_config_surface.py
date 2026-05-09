from __future__ import annotations

"""Final owner for bootstrap config surface.

Physical ownership moved from `boot/*` to `bootstrap/*`.
Legacy boot surfaces remain thin compatibility shells.
"""

from dataclasses import dataclass
from typing import Optional
from pathlib import Path
import os

CANON_BOOTSTRAP_CONFIG_SURFACE_FINAL_OWNER = True
CANON_BOOTSTRAP_CONFIG_SURFACE = True
CANON_BOOTSTRAP_CONFIG_SURFACE_NO_RUNTIME_ASSEMBLY = True
CANONICAL_OWNER_BOOTSTRAP_PUBLIC_API = "runtime.bootstrap"


def _env_path(name: str, default: str) -> Path:
    raw = str(os.getenv(name, default)).strip() or default
    return Path(raw)


def _env_path_any(names: tuple[str, ...], default: str) -> Path:
    for name in names:
        raw = str(os.getenv(name, '')).strip()
        if raw:
            return Path(raw)
    return Path(default)


def _env_text(name: str, default: str) -> str:
    raw = str(os.getenv(name, default)).strip().lower()
    return raw or default


def _env_text_any(names: tuple[str, ...], default: str) -> str:
    for name in names:
        raw = str(os.getenv(name, '')).strip().lower()
        if raw:
            return raw
    return str(default).strip().lower() or default


def _env_int(name: str, default: int) -> int:
    raw = str(os.getenv(name, str(default))).strip()
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return int(default)
    return max(1, value)


@dataclass(frozen=True)
class BootstrapConfigSurface:
    data_dir: Path
    observability_data_dir: Path
    observability_store_mode: str
    action_audit_backend: str
    decision_audit_backend: str
    api_idempotency_path: Path
    action_audit_log_path: Path
    decision_audit_log_path: Path
    execution_trace_store_path: Path
    decision_trace_store_path: Path
    runtime_effect_trace_store_path: Path
    incident_signal_store_path: Path
    telemetry_event_store_path: Optional[Path] = None
    telemetry_event_store_backend: str = "sqlite"
    observability_export_dir: Path = Path(".runtime/observability/exports")
    observability_export_catalog_path: Path = Path(".runtime/observability/exports/bundle_catalog.json")
    observability_export_retention_count: int = 20
    audit_max_records: int = 5000
    audit_max_bytes: int = 2_000_000
    audit_backup_count: int = 2
    trace_max_records: int = 10000
    trace_max_bytes: int = 5_000_000
    trace_backup_count: int = 4

    def __post_init__(self) -> None:
        telemetry_path = self.telemetry_event_store_path
        if telemetry_path is None:
            telemetry_path = self.observability_data_dir / "telemetry_events.sqlite3"
        object.__setattr__(self, "telemetry_event_store_path", Path(telemetry_path))
        backend = str(self.telemetry_event_store_backend or "sqlite").strip().lower() or "sqlite"
        object.__setattr__(self, "telemetry_event_store_backend", backend)
        object.__setattr__(self, "observability_export_dir", Path(self.observability_export_dir))
        object.__setattr__(self, "observability_export_catalog_path", Path(self.observability_export_catalog_path))

    def snapshot(self) -> dict[str, str]:
        return {
            "data_dir": str(self.data_dir),
            "observability_data_dir": str(self.observability_data_dir),
            "observability_store_mode": str(self.observability_store_mode),
            "action_audit_backend": str(self.action_audit_backend),
            "decision_audit_backend": str(self.decision_audit_backend),
            "api_idempotency_path": str(self.api_idempotency_path),
            "action_audit_log_path": str(self.action_audit_log_path),
            "decision_audit_log_path": str(self.decision_audit_log_path),
            "execution_trace_store_path": str(self.execution_trace_store_path),
            "decision_trace_store_path": str(self.decision_trace_store_path),
            "runtime_effect_trace_store_path": str(self.runtime_effect_trace_store_path),
            "incident_signal_store_path": str(self.incident_signal_store_path),
            "telemetry_event_store_path": str(self.telemetry_event_store_path),
            "telemetry_event_store_backend": str(self.telemetry_event_store_backend),
            "observability_export_dir": str(self.observability_export_dir),
            "observability_export_catalog_path": str(self.observability_export_catalog_path),
            "observability_export_retention_count": str(self.observability_export_retention_count),
            "audit_max_records": str(self.audit_max_records),
            "audit_max_bytes": str(self.audit_max_bytes),
            "audit_backup_count": str(self.audit_backup_count),
            "trace_max_records": str(self.trace_max_records),
            "trace_max_bytes": str(self.trace_max_bytes),
            "trace_backup_count": str(self.trace_backup_count),
        }


def build_bootstrap_config_surface() -> BootstrapConfigSurface:
    data_dir = _env_path_any(("APP_RUNTIME_DATA_DIR", "BUSINESAIOS_DATA_DIR"), ".runtime")
    observability_data_dir = _env_path_any(("APP_OBSERVABILITY_DATA_DIR", "BUSINESAIOS_OBSERVABILITY_DATA_DIR"), str(data_dir / "observability"))
    observability_store_mode = _env_text_any(("APP_OBSERVABILITY_STORE_MODE", "BUSINESAIOS_OBSERVABILITY_STORE_MODE"), "sqlite")
    action_audit_backend = _env_text_any(("APP_ACTION_AUDIT_BACKEND", "BUSINESAIOS_ACTION_AUDIT_BACKEND"), observability_store_mode)
    decision_audit_backend = _env_text_any(("APP_DECISION_AUDIT_BACKEND", "BUSINESAIOS_DECISION_AUDIT_BACKEND"), observability_store_mode)
    export_dir = _env_path_any(("APP_OBSERVABILITY_EXPORT_DIR", "BUSINESAIOS_OBSERVABILITY_EXPORT_DIR"), str(observability_data_dir / "exports"))
    export_catalog_path = _env_path_any(("APP_OBSERVABILITY_EXPORT_CATALOG_PATH", "BUSINESAIOS_OBSERVABILITY_EXPORT_CATALOG_PATH"), str(export_dir / "bundle_catalog.json"))
    telemetry_backend = _env_text_any(("APP_TELEMETRY_EVENT_STORE_BACKEND", "BUSINESAIOS_TELEMETRY_EVENT_STORE_BACKEND"), observability_store_mode)
    return BootstrapConfigSurface(
        data_dir=data_dir,
        observability_data_dir=observability_data_dir,
        observability_store_mode=observability_store_mode,
        action_audit_backend=action_audit_backend,
        decision_audit_backend=decision_audit_backend,
        api_idempotency_path=_env_path_any(("APP_API_IDEMPOTENCY_PATH", "BUSINESAIOS_API_IDEMPOTENCY_PATH"), str(data_dir / "api_idempotency.sqlite3")),
        action_audit_log_path=_env_path_any(("APP_ACTION_AUDIT_LOG_PATH", "BUSINESAIOS_ACTION_AUDIT_LOG_PATH"), str(observability_data_dir / "action_audit.jsonl")),
        decision_audit_log_path=_env_path_any(("APP_DECISION_AUDIT_LOG_PATH", "BUSINESAIOS_DECISION_AUDIT_LOG_PATH"), str(observability_data_dir / "decision_audit.jsonl")),
        execution_trace_store_path=_env_path_any(("APP_EXECUTION_TRACE_STORE_PATH", "BUSINESAIOS_EXECUTION_TRACE_STORE_PATH"), str(observability_data_dir / "execution_traces.sqlite3")),
        decision_trace_store_path=_env_path_any(("APP_DECISION_TRACE_STORE_PATH", "BUSINESAIOS_DECISION_TRACE_STORE_PATH"), str(observability_data_dir / "decision_traces.sqlite3")),
        runtime_effect_trace_store_path=_env_path_any(("APP_RUNTIME_EFFECT_TRACE_STORE_PATH", "BUSINESAIOS_RUNTIME_EFFECT_TRACE_STORE_PATH"), str(observability_data_dir / "runtime_effect_traces.sqlite3")),
        incident_signal_store_path=_env_path_any(("APP_INCIDENT_SIGNAL_STORE_PATH", "BUSINESAIOS_INCIDENT_SIGNAL_STORE_PATH"), str(observability_data_dir / "incident_signals.sqlite3")),
        telemetry_event_store_path=_env_path_any(("APP_TELEMETRY_EVENT_STORE_PATH", "BUSINESAIOS_TELEMETRY_EVENT_STORE_PATH"), str(observability_data_dir / "telemetry_events.sqlite3")),
        telemetry_event_store_backend=telemetry_backend,
        observability_export_dir=export_dir,
        observability_export_catalog_path=export_catalog_path,
        observability_export_retention_count=_env_int("APP_OBSERVABILITY_EXPORT_RETENTION_COUNT", 20),
        audit_max_records=_env_int("APP_AUDIT_MAX_RECORDS", 5000),
        audit_max_bytes=_env_int("APP_AUDIT_MAX_BYTES", 2_000_000),
        audit_backup_count=_env_int("APP_AUDIT_BACKUP_COUNT", 2),
        trace_max_records=_env_int("APP_TRACE_MAX_RECORDS", 10000),
        trace_max_bytes=_env_int("APP_TRACE_MAX_BYTES", 5_000_000),
        trace_backup_count=_env_int("APP_TRACE_BACKUP_COUNT", 4),
    )


__all__ = [
    "CANON_BOOTSTRAP_CONFIG_SURFACE_FINAL_OWNER",
    "CANON_BOOTSTRAP_CONFIG_SURFACE_NO_RUNTIME_ASSEMBLY",
    "CANONICAL_OWNER_BOOTSTRAP_PUBLIC_API",
    "BootstrapConfigSurface",
    "build_bootstrap_config_surface",
]
