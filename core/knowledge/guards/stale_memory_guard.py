from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ..errors import StaleMemoryError
from ..types import MemoryRetrieval, StrategyMemoryEntry


@dataclass(frozen=True)
class StaleMemoryGuard:
    def ensure_entries_are_fresh(self, retrieval: MemoryRetrieval, entries: Sequence[StrategyMemoryEntry]) -> None:
        if not entries:
            return
        stale_ids = [entry.entity_id for entry in entries if entry.freshness_score < retrieval.min_freshness_score]
        if retrieval.strict_mode and stale_ids:
            raise StaleMemoryError(
                f"Knowledge retrieval contains stale entries below threshold: {', '.join(stale_ids)}"
            )
