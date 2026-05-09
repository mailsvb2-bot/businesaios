from __future__ import annotations

"""Canonical runtime-owned telemetry helpers.

This module is the single owner for runtime telemetry spans and correlation-key
propagation helpers. Runtime execution surfaces may depend on it, but should
not re-implement span wiring locally.
"""

from dataclasses import dataclass, field
from typing import Any, Mapping

from runtime.observability.tracing import correlation_key_scope, span_with_sla


CANON_RUNTIME_TELEMETRY_OWNER = True


@dataclass(frozen=True)
class TelemetryEvent:
    name: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    tenant_id: str = ""
    correlation_id: str = ""


def emit_telemetry(event: TelemetryEvent | str, payload: Mapping[str, Any] | None = None, **metadata: Any) -> dict[str, Any]:
    if isinstance(event, TelemetryEvent):
        return {
            "name": event.name,
            "payload": dict(event.payload or {}),
            "tenant_id": event.tenant_id,
            "correlation_id": event.correlation_id,
        }
    return {"name": str(event), "payload": dict(payload or {}), **metadata}


def execute_total_span(
    *,
    event_log: Any,
    user_id: str,
    decision_id: str,
    correlation_id: str,
    correlation_key: str | None,
):
    return span_with_sla(
        event_log=event_log,
        stage="execute_total",
        user_id=user_id,
        decision_id=decision_id,
        correlation_id=correlation_id,
        correlation_key=correlation_key,
    )


def telegram_api_span(
    *,
    event_log: Any,
    user_id: str,
    decision_id: str | None,
    correlation_id: str | None,
):
    """Convenience span for telegram_api stage using current correlation_key."""
    from runtime.observability.tracing import get_correlation_key

    return span_with_sla(
        event_log=event_log,
        stage="telegram_api",
        user_id=user_id,
        decision_id=decision_id,
        correlation_id=correlation_id,
        correlation_key=get_correlation_key(),
    )


__all__ = [
    "CANON_RUNTIME_TELEMETRY_OWNER",
    "TelemetryEvent",
    "correlation_key_scope",
    "emit_telemetry",
    "execute_total_span",
    "telegram_api_span",
]
