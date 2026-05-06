from __future__ import annotations

"""Canonical execution span bridge.

CANON_COMPAT_SHIM = True

Binds together:
- distributed trace context;
- runtime latency span;
- append-only execution trace events.

Evidence-only. Never owns business decisions.
"""

from contextlib import ExitStack
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from core.tenancy.normalization import require_tenant_id
from observability.distributed_trace_context import (
    DistributedTraceContext,
    ensure_trace_context,
    get_current_trace_context,
    trace_context_scope,
)
from observability.execution_trace_contract import ExecutionTraceEvent, TraceStage
from runtime.observability.error_handling import swallow
from runtime.observability import Span

CANON_EXECUTION_SPAN = True


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _norm_text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _safe_dict(value: object | None) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _to_stage(value: TraceStage | str) -> TraceStage:
    if isinstance(value, TraceStage):
        return value
    normalized = str(value or "").strip()
    for item in TraceStage:
        if item.value == normalized:
            return item
    raise ValueError(f"unknown TraceStage: {value!r}")


def _emit_trace_store_append(store: Any, event: ExecutionTraceEvent) -> None:
    if store is None:
        return
    append = getattr(store, "append", None)
    if callable(append):
        append(event)


def _emit_runtime_event_log(*, event_log: Any, event_type: str, trace_context: DistributedTraceContext, payload: Mapping[str, Any] | None = None) -> None:
    if event_log is None:
        return
    emit = getattr(event_log, "emit", None)
    if not callable(emit):
        return
    emit(
        event_type=str(event_type),
        source="runtime_observability",
        user_id=str(trace_context.user_id or "system"),
        decision_id=str(trace_context.decision_id or "-"),
        correlation_id=str(trace_context.correlation_id or trace_context.trace_id),
        payload={
            "tenant_id": str(trace_context.tenant_id),
            "trace_id": str(trace_context.trace_id),
            "span_id": str(trace_context.span_id),
            "parent_span_id": trace_context.parent_span_id,
            "run_id": trace_context.run_id,
            "executor_name": trace_context.executor_name,
            "component": trace_context.component,
            **_safe_dict(payload),
        },
    )


@dataclass
class MonotonicSequence:
    start_at: int = 0
    _value: int = field(init=False, repr=False)

    def __post_init__(self) -> None:
        start = int(self.start_at)
        if start < 0:
            raise ValueError("start_at must be >= 0")
        self._value = start

    def next(self) -> int:
        current = int(self._value)
        self._value += 1
        return current


def seed_sequence_from_execution_store(*, execution_trace_store: Any, tenant_id: str, run_id: str) -> MonotonicSequence:
    tenant_id = require_tenant_id(tenant_id)
    run_id = str(_norm_text(run_id) or "")
    if not run_id:
        raise ValueError("run_id is required")
    try:
        if execution_trace_store is None:
            return MonotonicSequence()
        lister = getattr(execution_trace_store, "list_by_run", None)
        if not callable(lister):
            return MonotonicSequence()
        items = tuple(lister(tenant_id=tenant_id, run_id=run_id))
        if not items:
            return MonotonicSequence()
        return MonotonicSequence(start_at=max(int(item.sequence_no) for item in items) + 1)
    except Exception:
        swallow(__name__, "observability/execution_span.py")
        return MonotonicSequence()


def emit_execution_trace_event(
    *,
    execution_trace_store: Any,
    tenant_id: str,
    trace_id: str,
    run_id: str,
    sequence_no: int,
    stage: TraceStage | str,
    event_type: str,
    correlation_id: str | None = None,
    decision_id: str | None = None,
    action_id: str | None = None,
    executor_name: str | None = None,
    component: str | None = None,
    payload: Mapping[str, Any] | None = None,
    emitted_at: datetime | None = None,
) -> ExecutionTraceEvent:
    event = ExecutionTraceEvent(
        tenant_id=require_tenant_id(tenant_id),
        trace_id=str(_norm_text(trace_id) or ""),
        run_id=str(_norm_text(run_id) or ""),
        sequence_no=int(sequence_no),
        stage=_to_stage(stage),
        event_type=str(_norm_text(event_type) or ""),
        emitted_at=emitted_at or _utc_now(),
        correlation_id=_norm_text(correlation_id),
        decision_id=_norm_text(decision_id),
        action_id=_norm_text(action_id),
        executor_name=_norm_text(executor_name),
        component=_norm_text(component),
        payload=_safe_dict(payload),
    )
    event.validate()
    _emit_trace_store_append(execution_trace_store, event)
    return event


@dataclass
class ExecutionSpan:
    stage: TraceStage | str
    tenant_id: str
    run_id: str
    event_log: Any = None
    execution_trace_store: Any = None
    sequence: MonotonicSequence | None = None
    trace_context: DistributedTraceContext | None = None
    decision_id: str | None = None
    correlation_id: str | None = None
    action_id: str | None = None
    executor_name: str | None = None
    component: str | None = None
    user_id: str | None = None
    start_payload: Mapping[str, Any] | None = None
    success_payload: Mapping[str, Any] | None = None
    failure_payload_builder: Callable[[BaseException], Mapping[str, Any] | None] | None = None
    create_child_context: bool = True

    _stack: ExitStack | None = field(default=None, init=False, repr=False)
    _stage: TraceStage = field(default=TraceStage.EXECUTION, init=False, repr=False)
    _resolved_context: DistributedTraceContext | None = field(default=None, init=False, repr=False)
    _started_at: datetime = field(default_factory=_utc_now, init=False, repr=False)

    def __enter__(self) -> "ExecutionSpan":
        self.tenant_id = require_tenant_id(self.tenant_id)
        self.run_id = str(_norm_text(self.run_id) or "")
        if not self.run_id:
            raise ValueError("run_id is required")
        self._stage = _to_stage(self.stage)
        self._resolved_context = self._resolve_context()
        if self.sequence is None:
            self.sequence = seed_sequence_from_execution_store(
                execution_trace_store=self.execution_trace_store,
                tenant_id=self.tenant_id,
                run_id=self.run_id,
            )
        stack = ExitStack()
        stack.enter_context(trace_context_scope(self._resolved_context))
        stack.enter_context(
            Span(
                event_log=self.event_log,
                stage=self._stage.value,
                user_id=str(self._resolved_context.user_id or "system"),
                decision_id=self._resolved_context.decision_id,
                correlation_id=self._resolved_context.correlation_id or self._resolved_context.trace_id,
                correlation_key=self._resolved_context.trace_id,
                extra={
                    "tenant_id": str(self._resolved_context.tenant_id),
                    "trace_id": str(self._resolved_context.trace_id),
                    "span_id": str(self._resolved_context.span_id),
                    "parent_span_id": self._resolved_context.parent_span_id,
                    "run_id": self._resolved_context.run_id,
                    "executor_name": self._resolved_context.executor_name,
                    "component": self._resolved_context.component,
                },
            )
        )
        self._stack = stack
        self._emit_started(self._resolved_context)
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        ctx = self._resolved_context
        try:
            if ctx is not None:
                if exc is None:
                    self._emit_succeeded(ctx)
                else:
                    self._emit_failed(ctx, exc)
        finally:
            if self._stack is not None:
                self._stack.close()
                self._stack = None
        return False

    def _resolve_context(self) -> DistributedTraceContext:
        base_ctx = self.trace_context or get_current_trace_context()
        if base_ctx is None:
            return ensure_trace_context(
                tenant_id=self.tenant_id,
                run_id=self.run_id,
                decision_id=self.decision_id,
                correlation_id=self.correlation_id,
                user_id=self.user_id,
                executor_name=self.executor_name,
                component=self.component,
            )
        if self.create_child_context:
            child = base_ctx.child(component=self.component, executor_name=self.executor_name)
            return child.with_updates(
                run_id=_norm_text(base_ctx.run_id) or self.run_id,
                decision_id=_norm_text(base_ctx.decision_id) or _norm_text(self.decision_id),
                correlation_id=_norm_text(base_ctx.correlation_id) or _norm_text(self.correlation_id) or base_ctx.trace_id,
                user_id=_norm_text(base_ctx.user_id) or _norm_text(self.user_id),
            )
        return base_ctx.with_updates(
            run_id=_norm_text(base_ctx.run_id) or self.run_id,
            decision_id=_norm_text(base_ctx.decision_id) or _norm_text(self.decision_id),
            correlation_id=_norm_text(base_ctx.correlation_id) or _norm_text(self.correlation_id) or base_ctx.trace_id,
            user_id=_norm_text(base_ctx.user_id) or _norm_text(self.user_id),
            executor_name=_norm_text(base_ctx.executor_name) or _norm_text(self.executor_name),
            component=_norm_text(base_ctx.component) or _norm_text(self.component),
        )

    def _next_sequence(self) -> int:
        if self.sequence is None:
            self.sequence = MonotonicSequence()
        return self.sequence.next()

    def _emit_started(self, ctx: DistributedTraceContext) -> None:
        emit_execution_trace_event(
            execution_trace_store=self.execution_trace_store,
            tenant_id=ctx.tenant_id,
            trace_id=ctx.trace_id,
            run_id=str(ctx.run_id or self.run_id),
            sequence_no=self._next_sequence(),
            stage=self._stage,
            event_type="span_started",
            correlation_id=ctx.correlation_id,
            decision_id=ctx.decision_id,
            action_id=self.action_id,
            executor_name=ctx.executor_name,
            component=ctx.component,
            payload={
                "span_id": str(ctx.span_id),
                "parent_span_id": ctx.parent_span_id,
                "started_at": self._started_at.isoformat(),
                **_safe_dict(self.start_payload),
            },
        )
        _emit_runtime_event_log(
            event_log=self.event_log,
            event_type="execution_span_started",
            trace_context=ctx,
            payload={"stage": self._stage.value, "action_id": self.action_id, **_safe_dict(self.start_payload)},
        )

    def _emit_succeeded(self, ctx: DistributedTraceContext) -> None:
        emit_execution_trace_event(
            execution_trace_store=self.execution_trace_store,
            tenant_id=ctx.tenant_id,
            trace_id=ctx.trace_id,
            run_id=str(ctx.run_id or self.run_id),
            sequence_no=self._next_sequence(),
            stage=self._stage,
            event_type="span_succeeded",
            correlation_id=ctx.correlation_id,
            decision_id=ctx.decision_id,
            action_id=self.action_id,
            executor_name=ctx.executor_name,
            component=ctx.component,
            payload={"span_id": str(ctx.span_id), "completed_at": _utc_now().isoformat(), **_safe_dict(self.success_payload)},
        )
        _emit_runtime_event_log(
            event_log=self.event_log,
            event_type="execution_span_succeeded",
            trace_context=ctx,
            payload={"stage": self._stage.value, "action_id": self.action_id, **_safe_dict(self.success_payload)},
        )

    def _emit_failed(self, ctx: DistributedTraceContext, exc: BaseException) -> None:
        failure_payload = _safe_dict(self.failure_payload_builder(exc)) if self.failure_payload_builder is not None else {}
        emit_execution_trace_event(
            execution_trace_store=self.execution_trace_store,
            tenant_id=ctx.tenant_id,
            trace_id=ctx.trace_id,
            run_id=str(ctx.run_id or self.run_id),
            sequence_no=self._next_sequence(),
            stage=self._stage,
            event_type="span_failed",
            correlation_id=ctx.correlation_id,
            decision_id=ctx.decision_id,
            action_id=self.action_id,
            executor_name=ctx.executor_name,
            component=ctx.component,
            payload={
                "span_id": str(ctx.span_id),
                "failed_at": _utc_now().isoformat(),
                "error": type(exc).__name__,
                "message": str(exc),
                **failure_payload,
            },
        )
        _emit_runtime_event_log(
            event_log=self.event_log,
            event_type="execution_span_failed",
            trace_context=ctx,
            payload={"stage": self._stage.value, "action_id": self.action_id, "error": type(exc).__name__, "message": str(exc), **failure_payload},
        )


def execution_span(**kwargs) -> ExecutionSpan:
    return ExecutionSpan(**kwargs)


__all__ = [
    "CANON_EXECUTION_SPAN",
    "ExecutionSpan",
    "MonotonicSequence",
    "emit_execution_trace_event",
    "execution_span",
    "seed_sequence_from_execution_store",
]
