from __future__ import annotations

from dataclasses import dataclass
from time import time

CANON_RUNTIME_INFERENCE_CAPACITY_TRANSITION_JOURNAL = True


@dataclass(frozen=True)
class InferenceCapacityTransitionRecord:
    at_ts: float
    from_tier: str
    to_tier: str
    reason: str


class InferenceCapacityTransitionJournal:
    def __init__(self) -> None:
        self._records: list[InferenceCapacityTransitionRecord] = []

    def record(self, *, from_tier: str, to_tier: str, reason: str) -> None:
        self._records.append(InferenceCapacityTransitionRecord(time(), from_tier, to_tier, reason))

    def list_records(self) -> tuple[InferenceCapacityTransitionRecord, ...]:
        return tuple(self._records)
