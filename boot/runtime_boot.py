from __future__ import annotations

"""Legacy-visible runtime boot compatibility surface.

This file exists intentionally as a thin shim because regression gates require
a physical, surface-visible module at ``boot.runtime_boot`` while the final
owner stays in ``bootstrap.runtime_boot``. No assembly ownership lives here.
"""

from importlib import import_module
from typing import Any

CANON_LEGACY_BOOTSTRAP_SHIM = True
CANON_BOOT_HELPER_SURFACE = True
CANON_RUNTIME_BOOT_THIN_SHIM = True
CANON_RUNTIME_BOOT_NO_RUNTIME_ASSEMBLY = True
CANON_RUNTIME_BOOT_SURFACE_VISIBLE_PRESENCE = True
CANONICAL_OWNER_BOOTSTRAP_PUBLIC_API = "runtime.bootstrap"

# Explicit observability lock keys retained here so regression suites can verify
# that the legacy-visible surface does not become silent or partial.
RUNTIME_BOOT_OBSERVABILITY_KEYS: tuple[str, ...] = (
    "event_bus",
    "metrics",
    "tracer",
    "tenant_metrics_registry",
    "audit_export_service",
    "telemetry_event_store",
    "decision_audit_log",
    "action_audit_log",
    "execution_trace_store",
    "decision_trace_store",
    "runtime_effect_trace_store",
    "sli_collector",
    "alerting_policy",
    "incident_signal_store",
)


def _owner_module():
    return import_module("bootstrap.runtime_boot")


def build_runtime_boot_surface(*args: Any, **kwargs: Any):
    return getattr(_owner_module(), "build_runtime_boot_surface")(*args, **kwargs)


def build_runtime_orchestrator(*args: Any, **kwargs: Any):
    return getattr(_owner_module(), "build_runtime_orchestrator")(*args, **kwargs)


def __getattr__(name: str):
    if name == "RuntimeBootSurface":
        return getattr(_owner_module(), name)
    raise AttributeError(name)


__all__ = [
    "CANON_LEGACY_BOOTSTRAP_SHIM",
    "CANON_BOOT_HELPER_SURFACE",
    "CANON_RUNTIME_BOOT_THIN_SHIM",
    "CANON_RUNTIME_BOOT_NO_RUNTIME_ASSEMBLY",
    "CANON_RUNTIME_BOOT_SURFACE_VISIBLE_PRESENCE",
    "CANONICAL_OWNER_BOOTSTRAP_PUBLIC_API",
    "RUNTIME_BOOT_OBSERVABILITY_KEYS",
    "RuntimeBootSurface",
    "build_runtime_boot_surface",
    "build_runtime_orchestrator",
]
