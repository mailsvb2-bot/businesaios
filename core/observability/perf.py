"""Latency profiling facade. Re-exports from split modules."""

from __future__ import annotations

from typing import Any, Dict, Optional

from core.observability.perf_span import (
    Span,
    emit_sla_violation,
    set_sla_budget_ms,
    sla_budget_ms,
)
from core.observability.perf_span import (
    emit_span as _emit_span_core,
)
from core.observability.perf_utils import AutoAccelerator, stable_hash_01
from core.observability.perf_watchdog import (
    recent_sla_breaches,
    rolling_latency_summary,
    rolling_track,
    watchdog_tick,
)


def emit_span(
    *,
    event_log: Any,
    stage: str,
    duration_ms: int,
    user_id: str,
    decision_id: str | None = None,
    correlation_id: str | None = None,
    correlation_key: str | None = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Emit span and feed rolling tracker."""
    rolling_track(
        str(stage),
        str(correlation_key or ""),
        extra if isinstance(extra, dict) else None,
        int(duration_ms),
    )
    _emit_span_core(
        event_log=event_log,
        stage=stage,
        duration_ms=duration_ms,
        user_id=user_id,
        decision_id=decision_id,
        correlation_id=correlation_id,
        correlation_key=correlation_key,
        extra=extra,
    )


__all__ = [
    "Span",
    "emit_span",
    "emit_sla_violation",
    "sla_budget_ms",
    "set_sla_budget_ms",
    "recent_sla_breaches",
    "rolling_latency_summary",
    "watchdog_tick",
    "stable_hash_01",
    "AutoAccelerator",
]
