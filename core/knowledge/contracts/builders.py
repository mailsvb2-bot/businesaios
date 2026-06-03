"""Builder protocols for knowledge domain."""
from __future__ import annotations

from typing import Protocol
from collections.abc import Sequence

from ..types import (
    BusinessCase,
    Lesson,
    LessonDraft,
    MemoryRetrieval,
    MemorySummary,
    Pattern,
    PatternDraft,
    StrategyMemoryEntry,
)

__all__ = [
    "LessonBuilder",
    "PatternBuilder",
    "MemorySummaryBuilder",
    "BusinessCaseBuilder",
]


class LessonBuilder(Protocol):
    def build(self, draft: LessonDraft) -> Lesson: ...


class PatternBuilder(Protocol):
    def build(self, draft: PatternDraft) -> Pattern: ...


class MemorySummaryBuilder(Protocol):
    def build(
        self,
        retrieval: MemoryRetrieval,
        entries: Sequence[StrategyMemoryEntry],
    ) -> MemorySummary: ...


class BusinessCaseBuilder(Protocol):
    def build(
        self,
        lesson: Lesson,
        linked_patterns: Sequence[Pattern],
    ) -> BusinessCase: ...
