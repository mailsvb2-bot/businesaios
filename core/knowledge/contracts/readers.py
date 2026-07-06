"""Reader protocols for knowledge domain."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from ..types import (
    Lesson,
    LessonQuery,
    MemoryRetrieval,
    OutcomeFact,
    Pattern,
    StrategyMemoryEntry,
)

__all__ = [
    "LessonReader",
    "PatternReader",
    "OutcomeReader",
    "StrategyMemoryReader",
]


class LessonReader(Protocol):
    def get(self, lesson_id: str) -> Lesson | None: ...
    def search(self, query: LessonQuery) -> Sequence[Lesson]: ...


class PatternReader(Protocol):
    def get(self, pattern_id: str) -> Pattern | None: ...
    def find_by_subject(self, subject: str) -> Sequence[Pattern]: ...


class OutcomeReader(Protocol):
    def list_outcomes(self, entity_id: str) -> Sequence[OutcomeFact]: ...


class StrategyMemoryReader(Protocol):
    def retrieve(self, retrieval: MemoryRetrieval) -> Sequence[StrategyMemoryEntry]: ...
