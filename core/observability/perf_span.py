"""Span emission and SLA budget. No rolling/watchdog logic."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

_SLA_BUTTON_BUDGET_MS: int = 300


def set_sla_budget_ms(value: int) -> None:
    """Inject SLA budget for button latency profiling (runtime-configured)."""
    try:
        v = int(value)
    except (TypeError, ValueError):
        v = 300
    v = max(50, min(10_000, v))
    global _SLA_BUTTON_BUDGET_MS
    _SLA_BUTTON_BUDGET_MS = int(v)


def sla_budget_ms() -> int:
    return int(_SLA_BUTTON_BUDGET_MS)


def emit_span(
    *,
    event_log: Any,
    stage: str,
    duration_ms: int,
    user_id: str,
    decision_id: str | None = None,
    correlation_id: str | None = None,
    correlation_key: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Core span emission (no rolling track). Caller or perf.py wires rolling."""
    try:
        if event_log is None or not hasattr(event_log, "emit"):
            return
        payload: dict[str, Any] = {
            "stage": str(stage),
            "duration_ms": int(max(0, int(duration_ms))),
        }
        if correlation_key:
            payload["correlation_key"] = str(correlation_key)
        if isinstance(extra, dict) and extra:
            payload["extra"] = {str(k): v for k, v in list(extra.items())[:30]}

        event_log.emit(
            event_type="latency_span",
            source="perf",
            user_id=str(user_id or "unknown"),
            decision_id=str(decision_id or "-"),
            correlation_id=str(correlation_id or (decision_id or "-")),
            payload=payload,
        )
    except Exception:
        return


@dataclass
class Span:
    event_log: Any
    stage: str
    user_id: str
    decision_id: str | None = None
    correlation_id: str | None = None
    correlation_key: str | None = None
    extra: dict[str, Any] | None = None

    _t0_ns: int = 0

    def __enter__(self):
        self._t0_ns = time.perf_counter_ns()
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            dt_ms = int((time.perf_counter_ns() - int(self._t0_ns)) / 1_000_000)
        except (TypeError, ValueError):
            dt_ms = 0
        emit_span(
            event_log=self.event_log,
            stage=self.stage,
            duration_ms=dt_ms,
            user_id=self.user_id,
            decision_id=self.decision_id,
            correlation_id=self.correlation_id,
            correlation_key=self.correlation_key,
            extra=self.extra,
        )
        return False


def emit_sla_violation(
    *,
    event_log: Any,
    stage: str,
    duration_ms: int,
    user_id: str,
    decision_id: str | None,
    correlation_id: str | None,
    correlation_key: str | None,
) -> None:
    try:
        if duration_ms < sla_budget_ms():
            return
        if event_log is None or not hasattr(event_log, "emit"):
            return
        event_log.emit(
            event_type="sla_violation",
            source="perf",
            user_id=str(user_id or "unknown"),
            decision_id=str(decision_id or "-"),
            correlation_id=str(correlation_id or (decision_id or "-")),
            payload={
                "stage": str(stage),
                "duration_ms": int(duration_ms),
                "budget_ms": int(sla_budget_ms()),
                "correlation_key": str(correlation_key) if correlation_key else None,
                "ts_ms": int(time.time() * 1000),
            },
        )
    except Exception:
        return


__all__ = ["Span", "emit_span", "emit_sla_violation", "sla_budget_ms", "set_sla_budget_ms"]
