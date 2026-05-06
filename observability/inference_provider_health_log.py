from __future__ import annotations

from dataclasses import dataclass
from time import time


CANON_OBSERVABILITY_INFERENCE_PROVIDER_HEALTH_LOG = True


@dataclass(frozen=True)
class InferenceProviderHealthEvent:
    ts: float
    provider_name: str
    healthy: bool
    error_rate: float


class InferenceProviderHealthLog:
    def __init__(self) -> None:
        self._events: list[InferenceProviderHealthEvent] = []

    def record(self, *, provider_name: str, healthy: bool, error_rate: float) -> None:
        self._events.append(InferenceProviderHealthEvent(time(), provider_name, healthy, error_rate))

    def list_events(self) -> tuple[InferenceProviderHealthEvent, ...]:
        return tuple(self._events)
