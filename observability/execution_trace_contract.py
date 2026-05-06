from __future__ import annotations

"""Canonical trace contracts for execution / decision / runtime effects.

CANON_COMPAT_SHIM = True

This module is evidence-only.
It must never become a second decision center.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Protocol

from core.tenancy.normalization import require_tenant_id


CANON_EXECUTION_TRACE_CONTRACT = True


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TraceStage(str, Enum):
    REQUEST = "request"
    WORLD_STATE = "world_state"
    DECISION = "decision"
    EXECUTABLE_ACTION = "executable_action"
    EXECUTION = "execution"
    VERIFICATION = "verification"
    STATE_UPDATE = "state_update"
    EVIDENCE = "evidence"
    COMPLETED = "completed"
    FAILED = "failed"


class EffectDisposition(str, Enum):
    PLANNED = "planned"
    ATTEMPTED = "attempted"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    VERIFIED = "verified"
    REJECTED = "rejected"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class ExecutionTraceEvent:
    tenant_id: str
    trace_id: str
    run_id: str
    sequence_no: int
    stage: TraceStage
    event_type: str
    emitted_at: datetime = field(default_factory=utc_now)
    correlation_id: str | None = None
    decision_id: str | None = None
    action_id: str | None = None
    executor_name: str | None = None
    component: str | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if not str(self.trace_id or '').strip():
            raise ValueError('trace_id is required')
        if not str(self.run_id or '').strip():
            raise ValueError('run_id is required')
        if int(self.sequence_no) < 0:
            raise ValueError('sequence_no must be >= 0')
        if not str(self.event_type or '').strip():
            raise ValueError('event_type is required')
        if self.emitted_at.tzinfo is None:
            raise ValueError('emitted_at must be timezone-aware')


@dataclass(frozen=True)
class DecisionTraceEvent:
    tenant_id: str
    trace_id: str
    decision_id: str
    emitted_at: datetime = field(default_factory=utc_now)
    correlation_id: str | None = None
    policy_id: str | None = None
    route_name: str | None = None
    selected_action: str | None = None
    rationale_summary: str | None = None
    candidate_count: int | None = None
    component: str | None = None
    evidence_refs: tuple[str, ...] = ()
    payload: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if not str(self.trace_id or '').strip():
            raise ValueError('trace_id is required')
        if not str(self.decision_id or '').strip():
            raise ValueError('decision_id is required')
        if self.candidate_count is not None and int(self.candidate_count) < 0:
            raise ValueError('candidate_count must be >= 0')
        if self.emitted_at.tzinfo is None:
            raise ValueError('emitted_at must be timezone-aware')


@dataclass(frozen=True)
class RuntimeEffectTraceEvent:
    tenant_id: str
    trace_id: str
    effect_id: str
    effect_type: str
    disposition: EffectDisposition
    emitted_at: datetime = field(default_factory=utc_now)
    correlation_id: str | None = None
    decision_id: str | None = None
    action_id: str | None = None
    connector_name: str | None = None
    external_reference: str | None = None
    idempotency_key: str | None = None
    verification_reference: str | None = None
    component: str | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if not str(self.trace_id or '').strip():
            raise ValueError('trace_id is required')
        if not str(self.effect_id or '').strip():
            raise ValueError('effect_id is required')
        if not str(self.effect_type or '').strip():
            raise ValueError('effect_type is required')
        if self.emitted_at.tzinfo is None:
            raise ValueError('emitted_at must be timezone-aware')


class ExecutionTraceStoreContract(Protocol):
    def append(self, event: ExecutionTraceEvent) -> None: ...
    def list_by_trace(self, *, tenant_id: str, trace_id: str) -> tuple[ExecutionTraceEvent, ...]: ...
    def list_by_run(self, *, tenant_id: str, run_id: str) -> tuple[ExecutionTraceEvent, ...]: ...
    def validate_chain(self) -> None: ...


class DecisionTraceStoreContract(Protocol):
    def append(self, event: DecisionTraceEvent) -> None: ...
    def list_by_trace(self, *, tenant_id: str, trace_id: str) -> tuple[DecisionTraceEvent, ...]: ...
    def get(self, *, tenant_id: str, decision_id: str) -> DecisionTraceEvent | None: ...
    def validate_chain(self) -> None: ...


class RuntimeEffectTraceStoreContract(Protocol):
    def append(self, event: RuntimeEffectTraceEvent) -> None: ...
    def list_by_trace(self, *, tenant_id: str, trace_id: str) -> tuple[RuntimeEffectTraceEvent, ...]: ...
    def list_by_effect_type(self, *, tenant_id: str, effect_type: str, limit: int = 200) -> tuple[RuntimeEffectTraceEvent, ...]: ...
    def validate_chain(self) -> None: ...


__all__ = [
    'CANON_EXECUTION_TRACE_CONTRACT',
    'DecisionTraceEvent',
    'DecisionTraceStoreContract',
    'EffectDisposition',
    'ExecutionTraceEvent',
    'ExecutionTraceStoreContract',
    'RuntimeEffectTraceEvent',
    'RuntimeEffectTraceStoreContract',
    'TraceStage',
    'utc_now',
]
