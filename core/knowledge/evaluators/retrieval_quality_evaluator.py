from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ..enums import ReuseSafety
from ..types import MemoryRetrieval, RetrievalQualityAssessment, StrategyMemoryEntry


@dataclass(frozen=True)
class RetrievalQualityEvaluator:
    def evaluate(self, retrieval: MemoryRetrieval, entries: Sequence[StrategyMemoryEntry]) -> RetrievalQualityAssessment:
        if not entries:
            return RetrievalQualityAssessment(
                item_count=0,
                quality_score=0.0,
                coverage_score=0.0,
                safety=ReuseSafety.BLOCKED,
                reason="No entries found.",
            )
        avg_relevance = sum(item.relevance_score for item in entries) / len(entries)
        avg_freshness = sum(item.freshness_score for item in entries) / len(entries)
        avg_confidence = sum(item.confidence_score for item in entries) / len(entries)
        avg_support = sum(item.support_count for item in entries) / len(entries)
        quality_score = round(
            avg_relevance * 0.40 + avg_freshness * 0.20 + avg_confidence * 0.25 + min(avg_support / 3.0, 1.0) * 0.15,
            4,
        )
        coverage_score = round(min(len(entries) / max(retrieval.max_items, 1), 1.0), 4)
        if quality_score >= 0.75:
            safety = ReuseSafety.SAFE
        elif quality_score >= 0.50:
            safety = ReuseSafety.CAUTION
        else:
            safety = ReuseSafety.BLOCKED
        return RetrievalQualityAssessment(
            item_count=len(entries),
            quality_score=quality_score,
            coverage_score=coverage_score,
            safety=safety,
            reason="Composite score from relevance, freshness, confidence, and support density.",
        )
