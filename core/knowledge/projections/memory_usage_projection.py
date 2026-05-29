from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ..types import StrategyMemoryEntry


@dataclass(frozen=True)
class MemoryUsageProjection:
    entity_id: str
    kind: str
    relevance_score: float
    freshness_score: float
    confidence_score: float
    support_count: int

    @classmethod
    def from_entry(cls, entry: StrategyMemoryEntry) -> MemoryUsageProjection:
        return cls(
            entity_id=entry.entity_id,
            kind=entry.kind.value,
            relevance_score=entry.relevance_score,
            freshness_score=entry.freshness_score,
            confidence_score=entry.confidence_score,
            support_count=entry.support_count,
        )

    @classmethod
    def build_many(cls, entries: Sequence[StrategyMemoryEntry]) -> tuple[MemoryUsageProjection, ...]:
        return tuple(cls.from_entry(entry) for entry in entries)
