from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ..enums import KnowledgeKind
from ..errors import UnsafeReuseError
from ..types import MemoryRetrieval, StrategyMemoryEntry


@dataclass(frozen=True)
class UnsafeReuseGuard:
    def ensure_reuse_is_safe(self, retrieval: MemoryRetrieval, entries: Sequence[StrategyMemoryEntry]) -> None:
        if retrieval.strict_mode and not entries:
            raise UnsafeReuseError("Strict knowledge reuse requested, but no memory entries were retrieved.")
        low_relevance_ids = [entry.entity_id for entry in entries if entry.relevance_score < retrieval.min_relevance_score]
        if retrieval.strict_mode and low_relevance_ids:
            raise UnsafeReuseError(
                f"Knowledge reuse blocked due to low relevance entries: {', '.join(low_relevance_ids)}"
            )
        low_support_ids = [entry.entity_id for entry in entries if entry.support_count < retrieval.min_support_count]
        if retrieval.strict_mode and low_support_ids:
            raise UnsafeReuseError(
                f"Knowledge reuse blocked due to low support entries: {', '.join(low_support_ids)}"
            )
        has_lesson_support = any(entry.kind == KnowledgeKind.LESSON for entry in entries)
        if retrieval.strict_mode and not has_lesson_support:
            raise UnsafeReuseError(
                "Knowledge reuse blocked because retrieval has no lesson-level support."
            )
