from __future__ import annotations

from runtime.package_alias_namespace import build_package_alias_namespace

CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE = True
CANON_RUNTIME_OBSERVABILITY_PUBLIC_API = True

_PUBLIC_ATTRS = {
    "AutoAccelerator": ("core.observability.perf", "AutoAccelerator"), "CANON_RUNTIME_OBSERVABILITY_PUBLIC_API": ("runtime.observability", "CANON_RUNTIME_OBSERVABILITY_PUBLIC_API"),
    "JsonFormatter": ("core.observability.structured_logging", "JsonFormatter"), "Span": ("core.observability.perf", "Span"),
    "bind": ("core.observability.structured_logging", "bind"), "clear": ("core.observability.structured_logging", "clear"),
    "configure_structured_logging": ("core.observability.structured_logging", "configure_structured_logging"), "correlation_key_scope": ("runtime.observability.tracing", "correlation_key_scope"),
    "emit_span": ("core.observability.perf", "emit_span"), "emit_sla_violation": ("core.observability.perf", "emit_sla_violation"),
    "get_correlation_key": ("runtime.observability.tracing", "get_correlation_key"), "log_exception_throttled": ("core.observability.errors", "log_exception_throttled"),
    "recent_sla_breaches": ("core.observability.perf", "recent_sla_breaches"), "rolling_latency_summary": ("core.observability.perf", "rolling_latency_summary"),
    "set_sla_budget_ms": ("core.observability.perf", "set_sla_budget_ms"), "sla_budget_ms": ("core.observability.perf", "sla_budget_ms"),
    "snapshot": ("core.observability.structured_logging", "snapshot"), "span_with_sla": ("runtime.observability.tracing", "span_with_sla"),
    "stable_hash_01": ("core.observability.perf", "stable_hash_01"), "watchdog_tick": ("core.observability.perf", "watchdog_tick"),
}

__getattr__, __dir__, __all__ = build_package_alias_namespace(
    __name__,
    _PUBLIC_ATTRS,
    extra_exports=['CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE', 'CANON_RUNTIME_OBSERVABILITY_PUBLIC_API'],
    install_public_api=True
)
