from __future__ import annotations

import time

from core.decision.runtime_decision_trace import RuntimeDecisionTrace
from core.observability.perf import set_sla_budget_ms
from core.observability.telemetry import telegram_api_span as core_telegram_api_span
from runtime.execution.telemetry import (
    correlation_key_scope as execution_correlation_key_scope,
)
from runtime.execution.telemetry import (
    execute_total_span as execution_execute_total_span,
)
from runtime.execution.telemetry import (
    telegram_api_span as execution_telegram_api_span,
)
from runtime.observability.metrics import Metrics as RuntimeMetrics
from runtime.observability.telemetry import (
    correlation_key_scope as runtime_correlation_key_scope,
)
from runtime.observability.telemetry import (
    execute_total_span as runtime_execute_total_span,
)
from runtime.observability.telemetry import (
    telegram_api_span as runtime_telegram_api_span,
)
from runtime.platform.support.explainability.decision_trace import DecisionTrace as RuntimeCompatDecisionTrace
from runtime.platform.support.observability.metrics import Metrics as CompatMetrics


class _EventLog:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def emit(self, event_type: str | None = None, source: str | None = None, user_id: str | None = None, decision_id: str | None = None, correlation_id: str | None = None, payload: dict | None = None, **kwargs) -> None:
        event = {
            "event_type": event_type,
            "source": source,
            "user_id": user_id,
            "decision_id": decision_id,
            "correlation_id": correlation_id,
            "payload": dict(payload or {}),
        }
        event.update(kwargs)
        self.events.append(event)


def test_runtime_execution_telemetry_reexports_runtime_observability_owner() -> None:
    assert execution_correlation_key_scope is runtime_correlation_key_scope
    assert execution_execute_total_span is runtime_execute_total_span
    assert execution_telegram_api_span is runtime_telegram_api_span
    assert core_telegram_api_span is runtime_telegram_api_span


def test_runtime_metrics_support_surface_reexports_runtime_owner() -> None:
    assert CompatMetrics is RuntimeMetrics
    metrics = CompatMetrics()
    metrics.set("latency_ms", 12)
    assert metrics.get("latency_ms") == 12.0
    assert metrics.snapshot() == {"latency_ms": 12.0}


def test_runtime_decision_trace_support_surface_reexports_core_owner() -> None:
    assert RuntimeCompatDecisionTrace is RuntimeDecisionTrace
    trace = RuntimeCompatDecisionTrace()
    trace.add({"step": "scored", "score": 0.9})
    assert trace.events() == [{"step": "scored", "score": 0.9}]


def test_execute_total_span_preserves_runtime_span_behavior() -> None:
    event_log = _EventLog()
    set_sla_budget_ms(50)
    with execution_correlation_key_scope("ck-1"):
        with execution_execute_total_span(
            event_log=event_log,
            user_id="u1",
            decision_id="d1",
            correlation_id="c1",
            correlation_key="ck-1",
        ):
            time.sleep(0.06)
    assert any(evt.get("event_type") == "sla_violation" for evt in event_log.events)


def test_telegram_span_uses_current_correlation_key() -> None:
    event_log = _EventLog()
    set_sla_budget_ms(50)
    with execution_correlation_key_scope("ck-telegram"):
        with execution_telegram_api_span(
            event_log=event_log,
            user_id="u1",
            decision_id="d2",
            correlation_id="c2",
        ):
            time.sleep(0.06)
    sla_events = [evt for evt in event_log.events if evt.get("event_type") == "sla_violation"]
    assert sla_events
    assert sla_events[-1]["payload"].get("correlation_key") == "ck-telegram"
