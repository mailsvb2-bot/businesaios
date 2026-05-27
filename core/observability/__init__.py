"""Core-domain observability helpers with lazy public exports."""
from __future__ import annotations

import importlib
from typing import Any

CANON_COMPAT_SHIM = True
CANON_CORE_OBSERVABILITY_PUBLIC_API = True
_EXPORT_MAP = {
    "log_exception_throttled": "core.observability.errors",
    "Span": "core.observability.perf",
    "emit_sla_violation": "core.observability.perf",
    "swallow": "core.observability.silent",
    "bind": "core.observability.structured_logging",
    "clear": "core.observability.structured_logging",
    "log_exception_structured": "core.observability.structured_logging",
    "exception_throttled": "core.observability.throttled_logger",
    "warning_throttled": "core.observability.throttled_logger",
    "telemetry": "runtime.observability.telemetry",
}
_ATTR_ALIASES = {"log_exception_structured": "log_exception_throttled"}

def __getattr__(name: str) -> Any:
    if name in _EXPORT_MAP:
        module = importlib.import_module(_EXPORT_MAP[name])
        value = module if name == "telemetry" else getattr(module, _ATTR_ALIASES.get(name, name))
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = sorted(_EXPORT_MAP) + ["CANON_COMPAT_SHIM", "CANON_CORE_OBSERVABILITY_PUBLIC_API"]
