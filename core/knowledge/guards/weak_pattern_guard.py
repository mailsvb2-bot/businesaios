from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence

from ..enums import KnowledgeKind
from ..errors import WeakPatternError
from ..types import StrategyMemoryEntry


@dataclass(frozen=True)
class WeakPatternGuard:
    min_pattern_confidence: float = 0.55
    min_pattern_support_count: int = 1

    def ensure_entries_are_strong(self, entries: Sequence[StrategyMemoryEntry]) -> None:
        weak_pattern_ids = [
            entry.entity_id
            for entry in entries
            if entry.kind == KnowledgeKind.PATTERN
            and (
                entry.confidence_score < self.min_pattern_confidence
                or entry.support_count < self.min_pattern_support_count
            )
        ]
        if weak_pattern_ids:
            raise WeakPatternError(f"Weak patterns are not allowed for reuse: {', '.join(weak_pattern_ids)}")
