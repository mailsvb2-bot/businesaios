"""Explainer protocols for knowledge domain."""
from __future__ import annotations

from typing import Protocol

from ..types import (
    Lesson,
    LessonRelevanceAssessment,
    MemorySummary,
    Pattern,
    PatternConfidenceAssessment,
)

__all__ = [
    "MemoryTraceExplainer",
    "LessonUsageExplainer",
    "PatternConfidenceExplainer",
]


class MemoryTraceExplainer(Protocol):
    def explain(self, summary: MemorySummary) -> str: ...


class LessonUsageExplainer(Protocol):
    def explain(
        self,
        lesson: Lesson,
        assessment: LessonRelevanceAssessment,
    ) -> str: ...


class PatternConfidenceExplainer(Protocol):
    def explain(
        self,
        pattern: Pattern,
        assessment: PatternConfidenceAssessment,
    ) -> str: ...
