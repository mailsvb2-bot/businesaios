from __future__ import annotations

"""Canonical distributed trace context for runtime observability.

CANON_COMPAT_SHIM = True

Evidence-only surface:
- no business logic;
- no second orchestration path;
- one canonical owner for in-process trace propagation.
"""

import contextvars
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Iterator, Mapping

from core.tenancy.normalization import require_tenant_id

CANON_DISTRIBUTED_TRACE_CONTEXT = True


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _norm_text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _norm_bool(value: object | None, *, default: bool = True) -> bool:
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _norm_mapping(value: Mapping[str, object] | None) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    out: dict[str, str] = {}
    for key, item in value.items():
        k = _norm_text(key)
        v = _norm_text(item)
        if k is None or v is None:
            continue
        out[k] = v
    return out


def new_trace_id() -> str:
    return uuid.uuid4().hex


def new_span_id() -> str:
    return uuid.uuid4().hex[:16]


@dataclass(frozen=True)
class DistributedTraceContext:
    tenant_id: str
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    run_id: str | None = None
    decision_id: str | None = None
    correlation_id: str | None = None
    user_id: str | None = None
    executor_name: str | None = None
    component: str | None = None
    sampled: bool = True
    baggage: Mapping[str, str] = field(default_factory=dict)
    started_at: datetime = field(default_factory=_utc_now)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if _norm_text(self.trace_id) is None:
            raise ValueError("trace_id is required")
        if _norm_text(self.span_id) is None:
            raise ValueError("span_id is required")
        if self.started_at.tzinfo is None:
            raise ValueError("started_at must be timezone-aware")

    def as_headers(self) -> dict[str, str]:
        self.validate()
        headers = {
            "x-trace-id": str(self.trace_id),
            "x-span-id": str(self.span_id),
            "x-trace-sampled": "1" if self.sampled else "0",
            "x-tenant-id": str(self.tenant_id),
        }
        if self.parent_span_id:
            headers["x-parent-span-id"] = str(self.parent_span_id)
        if self.run_id:
            headers["x-run-id"] = str(self.run_id)
        if self.decision_id:
            headers["x-decision-id"] = str(self.decision_id)
        if self.correlation_id:
            headers["x-correlation-id"] = str(self.correlation_id)
        if self.user_id:
            headers["x-user-id"] = str(self.user_id)
        if self.executor_name:
            headers["x-executor-name"] = str(self.executor_name)
        if self.component:
            headers["x-component"] = str(self.component)
        for key, value in _norm_mapping(self.baggage).items():
            headers[f"x-baggage-{key}"] = value
        return headers

    def child(
        self,
        *,
        component: str | None = None,
        executor_name: str | None = None,
        baggage_updates: Mapping[str, object] | None = None,
    ) -> "DistributedTraceContext":
        merged_baggage = dict(_norm_mapping(self.baggage))
        merged_baggage.update(_norm_mapping(baggage_updates))
        child_ctx = replace(
            self,
            span_id=new_span_id(),
            parent_span_id=str(self.span_id),
            component=_norm_text(component) or self.component,
            executor_name=_norm_text(executor_name) or self.executor_name,
            baggage=merged_baggage,
            started_at=_utc_now(),
        )
        child_ctx.validate()
        return child_ctx

    def with_updates(self, **updates: object) -> "DistributedTraceContext":
        candidate = replace(self, **updates)
        candidate.validate()
        return candidate


_CURRENT_TRACE_CONTEXT: contextvars.ContextVar[DistributedTraceContext | None] = contextvars.ContextVar(
    "current_distributed_trace_context",
    default=None,
)


def get_current_trace_context() -> DistributedTraceContext | None:
    try:
        return _CURRENT_TRACE_CONTEXT.get()
    except Exception:
        return None


def set_current_trace_context(context: DistributedTraceContext | None):
    if context is not None:
        context.validate()
    return _CURRENT_TRACE_CONTEXT.set(context)


def reset_current_trace_context(token) -> None:
    _CURRENT_TRACE_CONTEXT.reset(token)


@contextmanager
def trace_context_scope(context: DistributedTraceContext | None) -> Iterator[DistributedTraceContext | None]:
    token = set_current_trace_context(context)
    try:
        yield context
    finally:
        reset_current_trace_context(token)


def build_trace_context(
    *,
    tenant_id: str,
    trace_id: str | None = None,
    span_id: str | None = None,
    parent_span_id: str | None = None,
    run_id: str | None = None,
    decision_id: str | None = None,
    correlation_id: str | None = None,
    user_id: str | None = None,
    executor_name: str | None = None,
    component: str | None = None,
    baggage: Mapping[str, object] | None = None,
    sampled: bool = True,
) -> DistributedTraceContext:
    ctx = DistributedTraceContext(
        tenant_id=require_tenant_id(tenant_id),
        trace_id=str(_norm_text(trace_id) or new_trace_id()),
        span_id=str(_norm_text(span_id) or new_span_id()),
        parent_span_id=_norm_text(parent_span_id),
        run_id=_norm_text(run_id),
        decision_id=_norm_text(decision_id),
        correlation_id=_norm_text(correlation_id),
        user_id=_norm_text(user_id),
        executor_name=_norm_text(executor_name),
        component=_norm_text(component),
        sampled=bool(sampled),
        baggage=_norm_mapping(baggage),
    )
    ctx.validate()
    return ctx


def ensure_trace_context(
    *,
    tenant_id: str,
    trace_id: str | None = None,
    run_id: str | None = None,
    decision_id: str | None = None,
    correlation_id: str | None = None,
    user_id: str | None = None,
    executor_name: str | None = None,
    component: str | None = None,
    baggage: Mapping[str, object] | None = None,
) -> DistributedTraceContext:
    current = get_current_trace_context()
    if current is not None:
        return current
    return build_trace_context(
        tenant_id=tenant_id,
        trace_id=trace_id,
        run_id=run_id,
        decision_id=decision_id,
        correlation_id=correlation_id,
        user_id=user_id,
        executor_name=executor_name,
        component=component,
        baggage=baggage,
    )


def child_trace_context(
    *,
    component: str | None = None,
    executor_name: str | None = None,
    baggage_updates: Mapping[str, object] | None = None,
) -> DistributedTraceContext | None:
    current = get_current_trace_context()
    if current is None:
        return None
    return current.child(component=component, executor_name=executor_name, baggage_updates=baggage_updates)


def inject_trace_headers(
    headers: Mapping[str, object] | None = None,
    *,
    context: DistributedTraceContext | None = None,
) -> dict[str, str]:
    merged = _norm_mapping(headers)
    ctx = context or get_current_trace_context()
    if ctx is None:
        return merged
    merged.update(ctx.as_headers())
    return merged


def extract_trace_context(
    headers: Mapping[str, object] | None,
    *,
    tenant_id: str | None = None,
    fallback_run_id: str | None = None,
    fallback_decision_id: str | None = None,
    fallback_correlation_id: str | None = None,
    fallback_user_id: str | None = None,
    fallback_executor_name: str | None = None,
    fallback_component: str | None = None,
    create_local_child_span: bool = True,
) -> DistributedTraceContext | None:
    normalized = {str(k).strip().lower(): v for k, v in dict(headers or {}).items()}
    resolved_tenant_id = _norm_text(tenant_id) or _norm_text(normalized.get("x-tenant-id"))
    if resolved_tenant_id is None:
        return None

    inbound_trace_id = _norm_text(normalized.get("x-trace-id"))
    inbound_span_id = _norm_text(normalized.get("x-span-id"))
    explicit_parent_span_id = _norm_text(normalized.get("x-parent-span-id"))

    baggage: dict[str, object] = {}
    for key, value in normalized.items():
        if key.startswith("x-baggage-"):
            baggage[key.removeprefix("x-baggage-")] = value

    if create_local_child_span:
        local_span_id = new_span_id()
        parent_span_id = inbound_span_id or explicit_parent_span_id
    else:
        local_span_id = inbound_span_id or new_span_id()
        parent_span_id = explicit_parent_span_id

    return build_trace_context(
        tenant_id=resolved_tenant_id,
        trace_id=inbound_trace_id or new_trace_id(),
        span_id=local_span_id,
        parent_span_id=parent_span_id,
        run_id=_norm_text(normalized.get("x-run-id")) or _norm_text(fallback_run_id),
        decision_id=_norm_text(normalized.get("x-decision-id")) or _norm_text(fallback_decision_id),
        correlation_id=_norm_text(normalized.get("x-correlation-id")) or _norm_text(fallback_correlation_id),
        user_id=_norm_text(normalized.get("x-user-id")) or _norm_text(fallback_user_id),
        executor_name=_norm_text(normalized.get("x-executor-name")) or _norm_text(fallback_executor_name),
        component=_norm_text(normalized.get("x-component")) or _norm_text(fallback_component),
        sampled=_norm_bool(normalized.get("x-trace-sampled"), default=True),
        baggage=baggage,
    )


def trace_context_from_envelope(
    env: Any,
    *,
    tenant_id: str,
    user_id: str | None = None,
    executor_name: str | None = None,
    component: str | None = "runtime_executor",
    baggage: Mapping[str, object] | None = None,
) -> DistributedTraceContext:
    decision = getattr(env, "decision", None)
    payload = getattr(decision, "payload", {}) or {}
    payload_map = dict(payload) if isinstance(payload, Mapping) else {}
    trace_id = (
        _norm_text(payload_map.get("trace_id"))
        or _norm_text(payload_map.get("execution_trace_id"))
        or _norm_text(payload_map.get("distributed_trace_id"))
        or _norm_text(getattr(decision, "correlation_id", None))
    )
    span_id = _norm_text(payload_map.get("span_id"))
    parent_span_id = _norm_text(payload_map.get("parent_span_id"))
    run_id = _norm_text(payload_map.get("run_id")) or _norm_text(getattr(env, "run_id", None)) or _norm_text(getattr(decision, "decision_id", None))
    decision_id = _norm_text(getattr(decision, "decision_id", None))
    correlation_id = _norm_text(getattr(decision, "correlation_id", None)) or _norm_text(payload_map.get("correlation_id")) or trace_id
    return build_trace_context(
        tenant_id=tenant_id,
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent_span_id,
        run_id=run_id,
        decision_id=decision_id,
        correlation_id=correlation_id,
        user_id=user_id,
        executor_name=executor_name,
        component=component,
        baggage=baggage,
    )


__all__ = [
    "CANON_DISTRIBUTED_TRACE_CONTEXT",
    "DistributedTraceContext",
    "build_trace_context",
    "child_trace_context",
    "ensure_trace_context",
    "extract_trace_context",
    "get_current_trace_context",
    "inject_trace_headers",
    "new_span_id",
    "new_trace_id",
    "reset_current_trace_context",
    "set_current_trace_context",
    "trace_context_from_envelope",
    "trace_context_scope",
]
