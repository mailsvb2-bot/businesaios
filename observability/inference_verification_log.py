from __future__ import annotations

from dataclasses import dataclass
from time import time


CANON_OBSERVABILITY_INFERENCE_VERIFICATION_LOG = True


@dataclass(frozen=True)
class InferenceVerificationEvent:
    ts: float
    provider_name: str
    accepted: bool
    reason: str


class InferenceVerificationLog:
    def __init__(self) -> None:
        self._events: list[InferenceVerificationEvent] = []

    def record(self, *, provider_name: str, accepted: bool, reason: str) -> None:
        self._events.append(InferenceVerificationEvent(time(), provider_name, accepted, reason))

    def list_events(self) -> tuple[InferenceVerificationEvent, ...]:
        return tuple(self._events)
