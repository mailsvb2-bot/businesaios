from __future__ import annotations

from observability.decision_trace_store import InMemoryDecisionTraceStore
from observability.distributed_trace_context import build_trace_context, extract_trace_context, inject_trace_headers
from observability.execution_span import execution_span
from observability.execution_trace_contract import (
    DecisionTraceEvent,
    EffectDisposition,
    RuntimeEffectTraceEvent,
    TraceStage,
)
from observability.execution_trace_store import InMemoryExecutionTraceStore
from observability.runtime_effect_trace_store import InMemoryRuntimeEffectTraceStore
from observability.runtime_trace_graph import RuntimeTraceGraphBuilder


class _EventLog:
    def __init__(self) -> None:
        self.items: list[dict] = []

    def emit(self, **payload):
        self.items.append(dict(payload))


def test_distributed_trace_context_extracts_local_child_span() -> None:
    parent = build_trace_context(tenant_id="tenant-a", trace_id="trace-1", span_id="span-parent", run_id="run-1")
    headers = inject_trace_headers(context=parent)

    child = extract_trace_context(headers, create_local_child_span=True)

    assert child is not None
    assert child.trace_id == "trace-1"
    assert child.span_id != "span-parent"
    assert child.parent_span_id == "span-parent"


def test_execution_span_appends_started_and_succeeded_events() -> None:
    store = InMemoryExecutionTraceStore()
    events = _EventLog()

    with execution_span(
        stage=TraceStage.EXECUTION,
        tenant_id="tenant-a",
        run_id="run-1",
        event_log=events,
        execution_trace_store=store,
        decision_id="decision-1",
        correlation_id="corr-1",
        action_id="action-1",
        executor_name="RuntimeExecutor",
        component="runtime.executor",
        start_payload={"x": 1},
        success_payload={"y": 2},
    ):
        pass

    rows = store.list_by_run(tenant_id="tenant-a", run_id="run-1")
    assert len(rows) == 2
    assert rows[0].event_type == "span_started"
    assert rows[1].event_type == "span_succeeded"
    assert len(events.items) >= 2


def test_runtime_trace_graph_builds_execution_decision_and_effect_edges() -> None:
    execution_store = InMemoryExecutionTraceStore()
    decision_store = InMemoryDecisionTraceStore()
    effect_store = InMemoryRuntimeEffectTraceStore()

    execution_store.append(
        __import__("observability.execution_trace_contract", fromlist=["ExecutionTraceEvent"]).ExecutionTraceEvent(
            tenant_id="tenant-a",
            trace_id="trace-1",
            run_id="run-1",
            sequence_no=0,
            stage=TraceStage.REQUEST,
            event_type="request_started",
            decision_id="decision-1",
            action_id="action-1",
            payload={"span_id": "span-1"},
        )
    )
    execution_store.append(
        __import__("observability.execution_trace_contract", fromlist=["ExecutionTraceEvent"]).ExecutionTraceEvent(
            tenant_id="tenant-a",
            trace_id="trace-1",
            run_id="run-1",
            sequence_no=1,
            stage=TraceStage.COMPLETED,
            event_type="request_completed",
            decision_id="decision-1",
            action_id="action-1",
            payload={"span_id": "span-2", "parent_span_id": "span-1"},
        )
    )
    decision_store.append(
        DecisionTraceEvent(
            tenant_id="tenant-a",
            trace_id="trace-1",
            decision_id="decision-1",
            selected_action="send_message",
        )
    )
    effect_store.append(
        RuntimeEffectTraceEvent(
            tenant_id="tenant-a",
            trace_id="trace-1",
            effect_id="effect-1",
            effect_type="telegram.send",
            disposition=EffectDisposition.SUCCEEDED,
            decision_id="decision-1",
            action_id="action-1",
        )
    )

    graph = RuntimeTraceGraphBuilder(
        execution_trace_store=execution_store,
        decision_trace_store=decision_store,
        runtime_effect_trace_store=effect_store,
    ).build_by_trace(tenant_id="tenant-a", trace_id="trace-1")

    summary = graph.summary()
    assert summary.execution_nodes == 2
    assert summary.decision_nodes == 1
    assert summary.effect_nodes == 1
    assert summary.has_request_stage is True
    assert summary.has_terminal_stage is True
    assert any(edge.relation == "decision_to_execution" for edge in graph.edges)
    assert any(edge.relation in {"execution_to_effect", "decision_to_effect"} for edge in graph.edges)
