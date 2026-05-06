"""Evaluator protocols for knowledge domain."""
from __future__ import annotations

from typing import Protocol, Sequence

from ..types import (
    Lesson,
    LessonRelevanceAssessment,
    MemoryRetrieval,
    Pattern,
    PatternConfidenceAssessment,
    RetrievalQualityAssessment,
    StrategyMemoryEntry,
)

__all__ = [
    "LessonRelevanceEvaluator",
    "PatternConfidenceEvaluator",
    "RetrievalQualityEvaluator",
]


class LessonRelevanceEvaluator(Protocol):
    def evaluate(
        self,
        retrieval: MemoryRetrieval,
        lesson: Lesson,
    ) -> LessonRelevanceAssessment: ...


class PatternConfidenceEvaluator(Protocol):
    def evaluate(self, pattern: Pattern) -> PatternConfidenceAssessment: ...


class RetrievalQualityEvaluator(Protocol):
    def evaluate(
        self,
        retrieval: MemoryRetrieval,
        entries: Sequence[StrategyMemoryEntry],
    ) -> RetrievalQualityAssessment: ...
