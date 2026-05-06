from __future__ import annotations

"""Canonical core-owned AI decision trace surface.

This module owns the mutable trace-building mechanics used by the sovereign
AI DecisionCore path. Historical imports from ``core.ai.decision_trace`` are
kept as compatibility shims only.
"""

import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class TraceStep:
    name: str
    input: Dict[str, Any]
    output: Dict[str, Any]
    duration_ms: int = 0


@dataclass(frozen=True)
class DecisionTrace:
    trace_id: str
    decision_id: str | None
    correlation_id: str | None
    user_id: str
    issued_at_ms: int
    steps: List[TraceStep]
    meta: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "decision_id": self.decision_id,
            "correlation_id": self.correlation_id,
            "user_id": self.user_id,
            "issued_at_ms": self.issued_at_ms,
            "steps": [asdict(s) for s in self.steps],
            "meta": dict(self.meta or {}),
        }


class TraceBuilder:
    """Tiny mutable builder owned by the canonical core decision layer."""

    def __init__(self, *, user_id: str, correlation_id: Optional[str]):
        self._trace_id = str(uuid.uuid4())
        self._user_id = str(user_id)
        self._correlation_id = str(correlation_id) if correlation_id else None
        self._start_ms = int(time.time() * 1000)
        self._steps: List[TraceStep] = []
        self._meta: Dict[str, Any] = {}

    @property
    def trace_id(self) -> str:
        return self._trace_id

    def meta(self, **kv: Any) -> None:
        for k, v in kv.items():
            if v is None:
                continue
            self._meta[str(k)] = v

    def add_step(self, *, name: str, input: Dict[str, Any], output: Dict[str, Any], duration_ms: int = 0) -> None:
        self._steps.append(TraceStep(name=str(name), input=dict(input or {}), output=dict(output or {}), duration_ms=int(duration_ms or 0)))

    def try_add_step(self, *, name: str, input: Dict[str, Any], output: Dict[str, Any], duration_ms: int = 0) -> None:
        """Best-effort step add (never throws).

        Trace is an *auxiliary* artifact: DecisionCore must not fail if trace
        building fails. Exceptions are swallowed through the canonical core
        observability helper to preserve fail-closed decision semantics.
        """
        try:
            self.add_step(name=name, input=input, output=output, duration_ms=duration_ms)
        except Exception:
            from core.observability.silent import swallow

            swallow(__name__, "trace.try_add_step")

    def build(self, *, decision_id: str | None) -> DecisionTrace:
        return DecisionTrace(
            trace_id=self._trace_id,
            decision_id=decision_id,
            correlation_id=self._correlation_id,
            user_id=self._user_id,
            issued_at_ms=self._start_ms,
            steps=list(self._steps),
            meta=dict(self._meta),
        )


CANON_AI_DECISION_TRACE = True

__all__ = [
    "CANON_AI_DECISION_TRACE",
    "DecisionTrace",
    "TraceBuilder",
    "TraceStep",
]
