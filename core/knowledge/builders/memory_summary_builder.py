from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ..contracts import RetrievalQualityEvaluator
from ..types import MemoryRetrieval, MemorySummary, StrategyMemoryEntry


@dataclass(frozen=True)
class MemorySummaryBuilder:
    retrieval_quality_evaluator: RetrievalQualityEvaluator

    def build(self, retrieval: MemoryRetrieval, entries: Sequence[StrategyMemoryEntry]) -> MemorySummary:
        quality = self.retrieval_quality_evaluator.evaluate(retrieval, entries)
        lines = [
            f"Knowledge summary for subject='{retrieval.target_subject}' and task='{retrieval.task}'.",
            f"entries={len(entries)}",
            f"coverage_score={quality.coverage_score:.2f}",
            f"quality_score={quality.quality_score:.2f}",
            f"safety={quality.safety.value}",
        ]
        for index, entry in enumerate(entries, start=1):
            lines.append(
                f"{index}. [{entry.kind.value}] {entry.summary} "
                f"(relevance={entry.relevance_score:.2f}, freshness={entry.freshness_score:.2f}, "
                f"confidence={entry.confidence_score:.2f}, support={entry.support_count})"
            )
        return MemorySummary(
            retrieval=retrieval,
            entries=tuple(entries),
            summary_text="\n".join(lines),
            coverage_score=quality.coverage_score,
            quality_score=quality.quality_score,
            safety=quality.safety,
        )
