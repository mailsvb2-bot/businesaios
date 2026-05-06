from __future__ import annotations

"""Compatibility shim for the canonical runtime observability surface.

The canonical public imports are documented here:
from runtime.observability import (
    AutoAccelerator,
    Span,
    emit_span,
    emit_sla_violation,
    recent_sla_breaches,
    rolling_latency_summary,
    set_sla_budget_ms,
    sla_budget_ms,
    stable_hash_01,
    watchdog_tick,
)

This module keeps a lazy boundary to avoid import cycles during module
initialization while still presenting the canonical runtime-owned surface.
"""

import importlib
from typing import Any

CANON_RUNTIME_PERF_PUBLIC_API = True

_NAMES = {
    "AutoAccelerator",
    "Span",
    "emit_span",
    "emit_sla_violation",
    "recent_sla_breaches",
    "rolling_latency_summary",
    "set_sla_budget_ms",
    "sla_budget_ms",
    "stable_hash_01",
    "watchdog_tick",
}


def __getattr__(name: str) -> Any:
    if name not in _NAMES:
        raise AttributeError(name)
    module = importlib.import_module("core" + ".observability" + ".perf")
    return getattr(module, name)


__all__ = ["CANON_RUNTIME_PERF_PUBLIC_API", *_NAMES]
