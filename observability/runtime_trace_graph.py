from __future__ import annotations

"""End-to-end runtime trace graph builder.

CANON_COMPAT_SHIM = True

Evidence-only: reconstructs what happened from canonical stores.
Never becomes a planner.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

from core.tenancy.normalization import require_tenant_id
from observability.execution_trace_contract import DecisionTraceEvent, ExecutionTraceEvent, RuntimeEffectTraceEvent, TraceStage

CANON_RUNTIME_TRACE_GRAPH = True


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _norm_text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _safe_dict(value: object | None) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


@dataclass(frozen=True)
class TraceGraphNode:
    node_id: str
    kind: str
    tenant_id: str
    trace_id: str
    timestamp: datetime
    stage: str | None = None
    run_id: str | None = None
    decision_id: str | None = None
    action_id: str | None = None
    effect_id: str | None = None
    correlation_id: str | None = None
    parent_span_id: str | None = None
    span_id: str | None = None
    label: str | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "kind": self.kind,
            "tenant_id": self.tenant_id,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp.isoformat(),
            "stage": self.stage,
            "run_id": self.run_id,
            "decision_id": self.decision_id,
            "action_id": self.action_id,
            "effect_id": self.effect_id,
            "correlation_id": self.correlation_id,
            "parent_span_id": self.parent_span_id,
            "span_id": self.span_id,
            "label": self.label,
            "payload": dict(self.payload),
        }


@dataclass(frozen=True)
class TraceGraphEdge:
    source_node_id: str
    target_node_id: str
    relation: str

    def as_dict(self) -> dict[str, str]:
        return {
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "relation": self.relation,
        }


@dataclass(frozen=True)
class RuntimeTraceGraphSummary:
    tenant_id: str
    trace_id: str
    execution_nodes: int
    decision_nodes: int
    effect_nodes: int
    total_nodes: int
    total_edges: int
    run_ids: tuple[str, ...]
    decision_ids: tuple[str, ...]
    effect_ids: tuple[str, ...]
    has_request_stage: bool
    has_terminal_stage: bool
    warning_count: int
    orphan_count: int

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__ | {
            "run_ids": list(self.run_ids),
            "decision_ids": list(self.decision_ids),
            "effect_ids": list(self.effect_ids),
        }


@dataclass(frozen=True)
class RuntimeTraceGraph:
    tenant_id: str
    trace_id: str
    built_at: datetime
    nodes: tuple[TraceGraphNode, ...]
    edges: tuple[TraceGraphEdge, ...]
    run_ids: tuple[str, ...] = ()
    decision_ids: tuple[str, ...] = ()
    effect_ids: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    orphan_node_ids: tuple[str, ...] = ()

    def summary(self) -> RuntimeTraceGraphSummary:
        execution_nodes = tuple(node for node in self.nodes if node.kind == "execution")
        decision_nodes = tuple(node for node in self.nodes if node.kind == "decision")
        effect_nodes = tuple(node for node in self.nodes if node.kind == "effect")
        stages = {str(node.stage) for node in execution_nodes if node.stage}
        return RuntimeTraceGraphSummary(
            tenant_id=self.tenant_id,
            trace_id=self.trace_id,
            execution_nodes=len(execution_nodes),
            decision_nodes=len(decision_nodes),
            effect_nodes=len(effect_nodes),
            total_nodes=len(self.nodes),
            total_edges=len(self.edges),
            run_ids=self.run_ids,
            decision_ids=self.decision_ids,
            effect_ids=self.effect_ids,
            has_request_stage=TraceStage.REQUEST.value in stages,
            has_terminal_stage=bool({TraceStage.COMPLETED.value, TraceStage.FAILED.value} & stages),
            warning_count=len(self.warnings),
            orphan_count=len(self.orphan_node_ids),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "trace_id": self.trace_id,
            "built_at": self.built_at.isoformat(),
            "run_ids": list(self.run_ids),
            "decision_ids": list(self.decision_ids),
            "effect_ids": list(self.effect_ids),
            "warnings": list(self.warnings),
            "orphan_node_ids": list(self.orphan_node_ids),
            "summary": self.summary().as_dict(),
            "nodes": [node.as_dict() for node in self.nodes],
            "edges": [edge.as_dict() for edge in self.edges],
        }


def _execution_node_id(item: ExecutionTraceEvent) -> str:
    return f"execution:{item.trace_id}:{item.run_id}:{int(item.sequence_no)}:{item.event_type}"


def _decision_node_id(item: DecisionTraceEvent) -> str:
    return f"decision:{item.trace_id}:{item.decision_id}:{item.emitted_at.isoformat()}"


def _effect_node_id(item: RuntimeEffectTraceEvent) -> str:
    return f"effect:{item.trace_id}:{item.effect_id}:{item.disposition.value}:{item.emitted_at.isoformat()}"


class RuntimeTraceGraphBuilder:
    def __init__(self, *, execution_trace_store: Any, decision_trace_store: Any, runtime_effect_trace_store: Any) -> None:
        self._execution_trace_store = execution_trace_store
        self._decision_trace_store = decision_trace_store
        self._runtime_effect_trace_store = runtime_effect_trace_store

    def build_by_trace(self, *, tenant_id: str, trace_id: str) -> RuntimeTraceGraph:
        tenant_id = require_tenant_id(tenant_id)
        trace_id = str(_norm_text(trace_id) or "")
        if not trace_id:
            raise ValueError("trace_id is required")
        execution_events = tuple(self._list_by_trace(self._execution_trace_store, tenant_id=tenant_id, trace_id=trace_id))
        decision_events = tuple(self._list_by_trace(self._decision_trace_store, tenant_id=tenant_id, trace_id=trace_id))
        effect_events = tuple(self._list_by_trace(self._runtime_effect_trace_store, tenant_id=tenant_id, trace_id=trace_id))
        return self._assemble(tenant_id=tenant_id, trace_id=trace_id, execution_events=execution_events, decision_events=decision_events, effect_events=effect_events)

    def build_by_run(self, *, tenant_id: str, run_id: str) -> RuntimeTraceGraph:
        tenant_id = require_tenant_id(tenant_id)
        run_id = str(_norm_text(run_id) or "")
        if not run_id:
            raise ValueError("run_id is required")
        execution_events = tuple(self._list_by_run(self._execution_trace_store, tenant_id=tenant_id, run_id=run_id))
        trace_ids = {str(item.trace_id) for item in execution_events if _norm_text(item.trace_id) is not None}
        if not trace_ids:
            raise ValueError("no execution trace found for run_id")
        if len(trace_ids) != 1:
            raise ValueError("run_id resolved to multiple trace_ids")
        trace_id = next(iter(trace_ids))
        decision_events = tuple(self._list_by_trace(self._decision_trace_store, tenant_id=tenant_id, trace_id=trace_id))
        effect_events = tuple(self._list_by_trace(self._runtime_effect_trace_store, tenant_id=tenant_id, trace_id=trace_id))
        return self._assemble(tenant_id=tenant_id, trace_id=trace_id, execution_events=execution_events, decision_events=decision_events, effect_events=effect_events)

    def validate_end_to_end(self, *, graph: RuntimeTraceGraph, strict: bool = False) -> None:
        execution_nodes = [node for node in graph.nodes if node.kind == "execution"]
        if not execution_nodes:
            raise ValueError("trace graph has no execution nodes")
        node_ids = {node.node_id for node in graph.nodes}
        for edge in graph.edges:
            if edge.source_node_id not in node_ids:
                raise ValueError(f"edge source missing: {edge.source_node_id}")
            if edge.target_node_id not in node_ids:
                raise ValueError(f"edge target missing: {edge.target_node_id}")
        if strict:
            summary = graph.summary()
            if not summary.has_request_stage:
                raise ValueError("trace graph missing request stage")
            if not summary.has_terminal_stage:
                raise ValueError("trace graph missing completed/failed terminal stage")
            if summary.orphan_count:
                raise ValueError("trace graph contains orphan nodes")

    @staticmethod
    def _list_by_trace(store: Any, *, tenant_id: str, trace_id: str):
        if store is None:
            return ()
        fn = getattr(store, "list_by_trace", None)
        if not callable(fn):
            return ()
        return tuple(fn(tenant_id=tenant_id, trace_id=trace_id))

    @staticmethod
    def _list_by_run(store: Any, *, tenant_id: str, run_id: str):
        if store is None:
            return ()
        fn = getattr(store, "list_by_run", None)
        if not callable(fn):
            return ()
        return tuple(fn(tenant_id=tenant_id, run_id=run_id))

    def _assemble(self, *, tenant_id: str, trace_id: str, execution_events: Iterable[ExecutionTraceEvent], decision_events: Iterable[DecisionTraceEvent], effect_events: Iterable[RuntimeEffectTraceEvent]) -> RuntimeTraceGraph:
        execution_sorted = tuple(sorted(execution_events, key=lambda item: (int(item.sequence_no), item.emitted_at.isoformat(), str(item.event_type))))
        decision_sorted = tuple(sorted(decision_events, key=lambda item: (item.emitted_at.isoformat(), str(item.decision_id))))
        effect_sorted = tuple(sorted(effect_events, key=lambda item: (item.emitted_at.isoformat(), str(item.effect_id), str(item.disposition.value))))
        nodes: list[TraceGraphNode] = []
        edges: list[TraceGraphEdge] = []
        warnings: list[str] = []
        decision_nodes_by_decision_id: dict[str, TraceGraphNode] = {}
        execution_nodes_by_span_id: dict[str, list[TraceGraphNode]] = {}
        execution_nodes_by_decision_id: dict[str, list[TraceGraphNode]] = {}
        execution_nodes_by_action_id: dict[str, list[TraceGraphNode]] = {}
        execution_nodes_by_run_id: dict[str, list[TraceGraphNode]] = {}
        previous_execution_node: TraceGraphNode | None = None

        for item in execution_sorted:
            payload = _safe_dict(item.payload)
            node = TraceGraphNode(
                node_id=_execution_node_id(item),
                kind="execution",
                tenant_id=str(item.tenant_id),
                trace_id=str(item.trace_id),
                timestamp=item.emitted_at,
                stage=item.stage.value,
                run_id=str(item.run_id),
                decision_id=_norm_text(item.decision_id),
                action_id=_norm_text(item.action_id),
                correlation_id=_norm_text(item.correlation_id),
                parent_span_id=_norm_text(payload.get("parent_span_id")),
                span_id=_norm_text(payload.get("span_id")),
                label=str(item.event_type),
                payload=payload,
            )
            nodes.append(node)
            if node.span_id:
                execution_nodes_by_span_id.setdefault(str(node.span_id), []).append(node)
            if node.decision_id:
                execution_nodes_by_decision_id.setdefault(str(node.decision_id), []).append(node)
            if node.action_id:
                execution_nodes_by_action_id.setdefault(str(node.action_id), []).append(node)
            if node.run_id:
                execution_nodes_by_run_id.setdefault(str(node.run_id), []).append(node)
            if previous_execution_node is not None:
                edges.append(TraceGraphEdge(source_node_id=previous_execution_node.node_id, target_node_id=node.node_id, relation="execution_flow"))
            previous_execution_node = node

        for item in decision_sorted:
            node = TraceGraphNode(
                node_id=_decision_node_id(item),
                kind="decision",
                tenant_id=str(item.tenant_id),
                trace_id=str(item.trace_id),
                timestamp=item.emitted_at,
                decision_id=str(item.decision_id),
                correlation_id=_norm_text(item.correlation_id),
                label=str(item.selected_action or item.route_name or "decision"),
                payload=_safe_dict(item.payload),
            )
            nodes.append(node)
            decision_nodes_by_decision_id[str(item.decision_id)] = node

        for item in effect_sorted:
            node = TraceGraphNode(
                node_id=_effect_node_id(item),
                kind="effect",
                tenant_id=str(item.tenant_id),
                trace_id=str(item.trace_id),
                timestamp=item.emitted_at,
                decision_id=_norm_text(item.decision_id),
                action_id=_norm_text(item.action_id),
                effect_id=str(item.effect_id),
                correlation_id=_norm_text(item.correlation_id),
                label=f"{item.effect_type}:{item.disposition.value}",
                payload=_safe_dict(item.payload),
            )
            nodes.append(node)

        for node in nodes:
            if node.kind == "execution" and node.decision_id and node.decision_id in decision_nodes_by_decision_id:
                edges.append(TraceGraphEdge(source_node_id=decision_nodes_by_decision_id[node.decision_id].node_id, target_node_id=node.node_id, relation="decision_to_execution"))

        for effect in effect_sorted:
            effect_node_id = _effect_node_id(effect)
            anchor = None
            if _norm_text(effect.action_id) is not None:
                matches = execution_nodes_by_action_id.get(str(effect.action_id), [])
                if matches:
                    anchor = matches[-1]
            if anchor is None and _norm_text(effect.decision_id) is not None:
                matches = execution_nodes_by_decision_id.get(str(effect.decision_id), [])
                if matches:
                    anchor = matches[-1]
            if anchor is not None:
                edges.append(TraceGraphEdge(source_node_id=anchor.node_id, target_node_id=effect_node_id, relation="execution_to_effect"))
            elif _norm_text(effect.decision_id) is not None and str(effect.decision_id) in decision_nodes_by_decision_id:
                edges.append(TraceGraphEdge(source_node_id=decision_nodes_by_decision_id[str(effect.decision_id)].node_id, target_node_id=effect_node_id, relation="decision_to_effect"))
            else:
                warnings.append(f"orphan effect event: {effect.effect_id}")

        for node in nodes:
            if node.kind != "execution" or node.parent_span_id is None:
                continue
            parents = execution_nodes_by_span_id.get(str(node.parent_span_id), [])
            if parents:
                edges.append(TraceGraphEdge(source_node_id=parents[-1].node_id, target_node_id=node.node_id, relation="parent_span"))

        connected: set[str] = set()
        for edge in edges:
            connected.add(edge.source_node_id)
            connected.add(edge.target_node_id)
        orphan_node_ids = tuple(sorted(node.node_id for node in nodes if node.kind != "execution" and node.node_id not in connected))
        deduped_edges: list[TraceGraphEdge] = []
        seen: set[tuple[str, str, str]] = set()
        for edge in edges:
            key = (edge.source_node_id, edge.target_node_id, edge.relation)
            if key in seen:
                continue
            seen.add(key)
            deduped_edges.append(edge)
        return RuntimeTraceGraph(
            tenant_id=str(tenant_id),
            trace_id=str(trace_id),
            built_at=_utc_now(),
            nodes=tuple(sorted(nodes, key=lambda node: (node.timestamp.isoformat(), node.kind, node.node_id))),
            edges=tuple(deduped_edges),
            run_ids=tuple(sorted(execution_nodes_by_run_id.keys())),
            decision_ids=tuple(sorted(decision_nodes_by_decision_id.keys())),
            effect_ids=tuple(sorted(str(item.effect_id) for item in effect_sorted if _norm_text(item.effect_id) is not None)),
            warnings=tuple(warnings),
            orphan_node_ids=orphan_node_ids,
        )


__all__ = [
    "CANON_RUNTIME_TRACE_GRAPH",
    "RuntimeTraceGraph",
    "RuntimeTraceGraphBuilder",
    "RuntimeTraceGraphSummary",
    "TraceGraphEdge",
    "TraceGraphNode",
]
