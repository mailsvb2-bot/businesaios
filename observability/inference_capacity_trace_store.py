from __future__ import annotations

from dataclasses import dataclass


CANON_OBSERVABILITY_INFERENCE_CAPACITY_TRACE_STORE = True


@dataclass(frozen=True)
class InferenceCapacityTrace:
    decision_id: str
    tier: str
    provider_name: str
    reason: str


class InferenceCapacityTraceStore:
    def __init__(self) -> None:
        self._items: list[InferenceCapacityTrace] = []

    def append(self, trace: InferenceCapacityTrace) -> None:
        self._items.append(trace)

    def list_items(self) -> tuple[InferenceCapacityTrace, ...]:
        return tuple(self._items)
