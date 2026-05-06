from __future__ import annotations

"""Canonical runtime-owned telemetry helpers.

This module is the single owner for runtime telemetry spans and correlation-key
propagation helpers. Runtime execution surfaces may depend on it, but should
not re-implement span wiring locally.
"""

from typing import Any

from runtime.observability.tracing import correlation_key_scope, span_with_sla


CANON_RUNTIME_TELEMETRY_OWNER = True


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
    "correlation_key_scope",
    "execute_total_span",
    "telegram_api_span",
]
