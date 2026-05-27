from __future__ import annotations

"""Canonical runtime tracing helpers.

Goals:
- Single source of truth for correlation_key propagation.
- No ad-hoc contextvars scattered across modules.
- Minimal API used by executor, effects and transports.
"""

import contextvars
from contextlib import contextmanager
from typing import Any, Iterator

from runtime.observability.error_handling import swallow
from runtime.observability.perf import Span, emit_sla_violation

_current_correlation_key: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_correlation_key",
    default=None,
)


def get_correlation_key() -> str | None:
    try:
        return _current_correlation_key.get()
    except Exception:
        return None


def set_correlation_key(value: str | None):
    return _current_correlation_key.set(value if value is None else str(value))


def reset_correlation_key(token) -> None:
    _current_correlation_key.reset(token)


@contextmanager
def correlation_key_scope(value: str | None) -> Iterator[None]:
    tok = set_correlation_key(value)
    try:
        yield
    finally:
        reset_correlation_key(tok)


@contextmanager
def span_with_sla(
    *,
    event_log: Any,
    stage: str,
    user_id: str,
    decision_id: str | None = None,
    correlation_id: str | None = None,
    correlation_key: str | None = None,
    extra: dict | None = None,
) -> Iterator[Span]:
    """Span wrapper that always attempts to emit an SLA violation event."""

    with Span(
        event_log=event_log,
        stage=stage,
        user_id=user_id,
        decision_id=decision_id,
        correlation_id=correlation_id,
        correlation_key=correlation_key,
        extra=extra,
    ) as sp:
        try:
            yield sp
        finally:
            try:
                import time

                duration_ms = int((time.perf_counter_ns() - sp._t0_ns) / 1_000_000)  # type: ignore[attr-defined]
                emit_sla_violation(
                    event_log=event_log,
                    stage=stage,
                    duration_ms=duration_ms,
                    user_id=user_id,
                    decision_id=decision_id,
                    correlation_id=correlation_id,
                    correlation_key=correlation_key,
                )
            except Exception:
                swallow(__name__, 'runtime/observability/tracing.py')
