from __future__ import annotations

from dataclasses import dataclass
from time import time


CANON_OBSERVABILITY_INFERENCE_ESCALATION_AUDIT_LOG = True


@dataclass(frozen=True)
class InferenceEscalationAuditEvent:
    ts: float
    from_tier: str
    to_tier: str
    reason: str


class InferenceEscalationAuditLog:
    def __init__(self) -> None:
        self._events: list[InferenceEscalationAuditEvent] = []

    def record(self, *, from_tier: str, to_tier: str, reason: str) -> None:
        self._events.append(InferenceEscalationAuditEvent(time(), from_tier, to_tier, reason))

    def list_events(self) -> tuple[InferenceEscalationAuditEvent, ...]:
        return tuple(self._events)
