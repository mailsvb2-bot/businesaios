from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from observability.execution_trace_contract import (
    DecisionTraceEvent,
    EffectDisposition,
    ExecutionTraceEvent,
    RuntimeEffectTraceEvent,
    TraceStage,
)
from observability.runtime_trace_graph import (
    RuntimeTraceGraph,
    RuntimeTraceGraphBuilder,
    TraceGraphEdge,
    TraceGraphNode,
)


class _TraceStore:
    def __init__(self, *, by_trace=(), by_run=()) -> None:
        self.by_trace = tuple(by_trace)
        self.by_run = tuple(by_run)
        self.calls: list[tuple[str, str, str]] = []

    def list_by_trace(self, *, tenant_id: str, trace_id: str):
        self.calls.append(("trace", tenant_id, trace_id))
        return self.by_trace

    def list_by_run(self, *, tenant_id: str, run_id: str):
        self.calls.append(("run", tenant_id, run_id))
        return self.by_run


def _execution(
    *,
    sequence: int,
    stage: TraceStage,
    event_type: str,
    at: datetime,
    decision_id: str | None = "decision-1",
    action_id: str | None = "action-1",
    payload: object = None,
    tenant_id: str = "tenant-a",
    trace_id: str = "trace-a",
    run_id: str = "run-a",
) -> ExecutionTraceEvent:
    return ExecutionTraceEvent(
        tenant_id=tenant_id,
        trace_id=trace_id,
        run_id=run_id,
        sequence_no=sequence,
        stage=stage,
        event_type=event_type,
        emitted_at=at,
        correlation_id="correlation-1",
        decision_id=decision_id,
        action_id=action_id,
        payload={} if payload is None else payload,
    )


def _decision(*, at: datetime, decision_id: str = "decision-1", payload: object = None, tenant_id: str = "tenant-a", trace_id: str = "trace-a") -> DecisionTraceEvent:
    return DecisionTraceEvent(
        tenant_id=tenant_id,
        trace_id=trace_id,
        decision_id=decision_id,
        emitted_at=at,
        correlation_id="correlation-1",
        selected_action="send_message",
        route_name="fallback-route",
        payload={} if payload is None else payload,
    )


def _effect(
    *,
    at: datetime,
    effect_id: str,
    action_id: str | None = "action-1",
    decision_id: str | None = "decision-1",
    disposition: EffectDisposition = EffectDisposition.SUCCEEDED,
    payload: object = None,
    tenant_id: str = "tenant-a",
    trace_id: str = "trace-a",
) -> RuntimeEffectTraceEvent:
    return RuntimeEffectTraceEvent(
        tenant_id=tenant_id,
        trace_id=trace_id,
        effect_id=effect_id,
        effect_type="message",
        disposition=disposition,
        emitted_at=at,
        correlation_id="correlation-1",
        decision_id=decision_id,
        action_id=action_id,
        payload={} if payload is None else payload,
    )


def test_trace_graph_builds_links_summaries_and_serialization() -> None:
    base = datetime(2026, 7, 18, tzinfo=UTC)
    executions = (
        _execution(sequence=2, stage=TraceStage.COMPLETED, event_type="completed", at=base + timedelta(seconds=3), payload={"parent_span_id": "span-root", "span_id": "span-child"}),
        _execution(sequence=1, stage=TraceStage.REQUEST, event_type="requested", at=base + timedelta(seconds=1), payload={"span_id": "span-root"}),
    )
    decisions = (_decision(at=base + timedelta(seconds=2), payload="not-a-map"),)
    effects = (
        _effect(at=base + timedelta(seconds=4), effect_id="effect-action"),
        _effect(at=base + timedelta(seconds=5), effect_id="effect-decision", action_id=None),
        _effect(at=base + timedelta(seconds=6), effect_id="effect-orphan", action_id=None, decision_id=None, payload="bad"),
    )
    execution_store = _TraceStore(by_trace=executions, by_run=executions)
    builder = RuntimeTraceGraphBuilder(
        execution_trace_store=execution_store,
        decision_trace_store=_TraceStore(by_trace=decisions),
        runtime_effect_trace_store=_TraceStore(by_trace=effects),
    )
    graph = builder.build_by_trace(tenant_id=" tenant-a ", trace_id=" trace-a ")
    summary = graph.summary()
    assert summary.execution_nodes == 2
    assert summary.decision_nodes == 1
    assert summary.effect_nodes == 3
    assert summary.has_request_stage is True
    assert summary.has_terminal_stage is True
    assert summary.warning_count == 1
    assert summary.orphan_count == 1
    relations = {edge.relation for edge in graph.edges}
    assert {"execution_flow", "decision_to_execution", "execution_to_effect", "parent_span"} <= relations
    assert graph.run_ids == ("run-a",)
    assert graph.decision_ids == ("decision-1",)
    assert graph.effect_ids == ("effect-action", "effect-decision", "effect-orphan")
    payload = graph.as_dict()
    assert payload["summary"]["total_nodes"] == 6
    assert payload["nodes"] and payload["edges"]
    builder.validate_end_to_end(graph=graph)
    with pytest.raises(ValueError, match="orphan"):
        builder.validate_end_to_end(graph=graph, strict=True)

    by_run = builder.build_by_run(tenant_id="tenant-a", run_id="run-a")
    assert by_run.trace_id == "trace-a"
    assert execution_store.calls[-1] == ("run", "tenant-a", "run-a")


def test_trace_graph_validation_and_store_fallback_errors() -> None:
    builder = RuntimeTraceGraphBuilder(execution_trace_store=None, decision_trace_store=object(), runtime_effect_trace_store=None)
    with pytest.raises(ValueError, match="trace_id"):
        builder.build_by_trace(tenant_id="tenant-a", trace_id=" ")
    empty = builder.build_by_trace(tenant_id="tenant-a", trace_id="trace-a")
    with pytest.raises(ValueError, match="no execution"):
        builder.validate_end_to_end(graph=empty)
    with pytest.raises(ValueError, match="run_id"):
        builder.build_by_run(tenant_id="tenant-a", run_id=" ")
    with pytest.raises(ValueError, match="no execution trace"):
        builder.build_by_run(tenant_id="tenant-a", run_id="run-a")

    base = datetime(2026, 7, 18, tzinfo=UTC)
    multiple = _TraceStore(by_run=(
        _execution(sequence=1, stage=TraceStage.REQUEST, event_type="one", at=base, trace_id="trace-a"),
        _execution(sequence=2, stage=TraceStage.COMPLETED, event_type="two", at=base, trace_id="trace-b"),
    ))
    with pytest.raises(ValueError, match="multiple trace_ids"):
        RuntimeTraceGraphBuilder(execution_trace_store=multiple, decision_trace_store=None, runtime_effect_trace_store=None).build_by_run(tenant_id="tenant-a", run_id="run-a")

    node = TraceGraphNode(node_id="n", kind="execution", tenant_id="tenant-a", trace_id="trace-a", timestamp=base, stage=TraceStage.REQUEST.value)
    bad_source = RuntimeTraceGraph(tenant_id="tenant-a", trace_id="trace-a", built_at=base, nodes=(node,), edges=(TraceGraphEdge("missing", "n", "x"),))
    with pytest.raises(ValueError, match="edge source"):
        builder.validate_end_to_end(graph=bad_source)
    bad_target = RuntimeTraceGraph(tenant_id="tenant-a", trace_id="trace-a", built_at=base, nodes=(node,), edges=(TraceGraphEdge("n", "missing", "x"),))
    with pytest.raises(ValueError, match="edge target"):
        builder.validate_end_to_end(graph=bad_target)
    with pytest.raises(ValueError, match="terminal stage"):
        builder.validate_end_to_end(graph=RuntimeTraceGraph(tenant_id="tenant-a", trace_id="trace-a", built_at=base, nodes=(node,), edges=()), strict=True)
    terminal = TraceGraphNode(node_id="done", kind="execution", tenant_id="tenant-a", trace_id="trace-a", timestamp=base, stage=TraceStage.COMPLETED.value)
    with pytest.raises(ValueError, match="request stage"):
        builder.validate_end_to_end(graph=RuntimeTraceGraph(tenant_id="tenant-a", trace_id="trace-a", built_at=base, nodes=(terminal,), edges=()), strict=True)


def test_trace_graph_rejects_cross_tenant_and_cross_trace_store_leakage() -> None:
    base = datetime(2026, 7, 18, tzinfo=UTC)
    cross_tenant = _TraceStore(by_trace=(_execution(sequence=1, stage=TraceStage.REQUEST, event_type="x", at=base, tenant_id="tenant-b"),))
    builder = RuntimeTraceGraphBuilder(execution_trace_store=cross_tenant, decision_trace_store=None, runtime_effect_trace_store=None)
    with pytest.raises(ValueError, match="tenant_id"):
        builder.build_by_trace(tenant_id="tenant-a", trace_id="trace-a")

    cross_trace = _TraceStore(by_trace=(_decision(at=base, trace_id="trace-b"),))
    builder = RuntimeTraceGraphBuilder(execution_trace_store=None, decision_trace_store=cross_trace, runtime_effect_trace_store=None)
    with pytest.raises(ValueError, match="trace_id"):
        builder.build_by_trace(tenant_id="tenant-a", trace_id="trace-a")


def test_trace_graph_remaining_anchor_and_strict_success_branches() -> None:
    base = datetime(2026, 7, 18, tzinfo=UTC)
    executions = (
        _execution(sequence=1, stage=TraceStage.REQUEST, event_type="request", at=base, decision_id=None, action_id=None, payload={}),
        _execution(sequence=2, stage=TraceStage.COMPLETED, event_type="done", at=base + timedelta(seconds=1), decision_id="decision-2", action_id=None, payload={"parent_span_id": "missing-parent"}),
    )
    decisions = (_decision(at=base, decision_id="decision-2"),)
    effects = (_effect(at=base + timedelta(seconds=2), effect_id="effect-decision-only", action_id=None, decision_id="decision-2"),)
    builder = RuntimeTraceGraphBuilder(
        execution_trace_store=_TraceStore(by_trace=executions),
        decision_trace_store=_TraceStore(by_trace=decisions),
        runtime_effect_trace_store=_TraceStore(by_trace=effects),
    )
    graph = builder.build_by_trace(tenant_id="tenant-a", trace_id="trace-a")
    builder.validate_end_to_end(graph=graph, strict=True)
    assert "decision_to_effect" not in {edge.relation for edge in graph.edges}
    assert RuntimeTraceGraphBuilder._list_by_run(object(), tenant_id="tenant-a", run_id="run-a") == ()


def test_trace_graph_decision_only_anchor_duplicate_edge_and_empty_run_id() -> None:
    base = datetime(2026, 7, 18, tzinfo=UTC)
    executions = (
        _execution(sequence=1, stage=TraceStage.REQUEST, event_type="request", at=base, decision_id=None, action_id=None, run_id=""),
        _execution(sequence=2, stage=TraceStage.COMPLETED, event_type="done", at=base + timedelta(seconds=1), decision_id=None, action_id=None, run_id=""),
    )
    decisions = (_decision(at=base, decision_id="decision-only"),)
    duplicate_effect = _effect(at=base + timedelta(seconds=2), effect_id="effect-same", action_id="missing-action", decision_id="decision-only")
    effects = (duplicate_effect, duplicate_effect)
    graph = RuntimeTraceGraphBuilder(
        execution_trace_store=_TraceStore(by_trace=executions),
        decision_trace_store=_TraceStore(by_trace=decisions),
        runtime_effect_trace_store=_TraceStore(by_trace=effects),
    ).build_by_trace(tenant_id="tenant-a", trace_id="trace-a")
    assert graph.run_ids == ()
    decision_edges = [edge for edge in graph.edges if edge.relation == "decision_to_effect"]
    assert len(decision_edges) == 1
