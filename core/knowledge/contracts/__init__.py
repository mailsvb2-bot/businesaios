"""Knowledge domain contracts — protocol definitions.

Split into submodules by role:
  repositories  — LessonRepository, PatternRepository, MemoryLinkRepository
  readers       — LessonReader, PatternReader, OutcomeReader, StrategyMemoryReader
  writers       — LessonWriter, PatternWriter, MemoryLinkWriter
  builders      — LessonBuilder, PatternBuilder, MemorySummaryBuilder, BusinessCaseBuilder
  evaluators    — LessonRelevanceEvaluator, PatternConfidenceEvaluator, RetrievalQualityEvaluator
  explainers    — MemoryTraceExplainer, LessonUsageExplainer, PatternConfidenceExplainer
  guards        — KnowledgeGuard
  publishers    — EventPublisher
"""
from __future__ import annotations

from .builders import (
    BusinessCaseBuilder,
    LessonBuilder,
    MemorySummaryBuilder,
    PatternBuilder,
)
from .evaluators import (
    LessonRelevanceEvaluator,
    PatternConfidenceEvaluator,
    RetrievalQualityEvaluator,
)
from .explainers import (
    LessonUsageExplainer,
    MemoryTraceExplainer,
    PatternConfidenceExplainer,
)
from .guards import KnowledgeGuard
from .publishers import EventPublisher
from .readers import (
    LessonReader,
    OutcomeReader,
    PatternReader,
    StrategyMemoryReader,
)
from .repositories import (
    LessonRepository,
    MemoryLinkRepository,
    PatternRepository,
)
from .writers import (
    LessonWriter,
    MemoryLinkWriter,
    PatternWriter,
)

CANON_COMPAT_SHIM = True

__all__ = [
    "BusinessCaseBuilder",
    "CANON_COMPAT_SHIM",
    "EventPublisher",
    "KnowledgeGuard",
    "LessonBuilder",
    "LessonReader",
    "LessonRelevanceEvaluator",
    "LessonRepository",
    "LessonUsageExplainer",
    "LessonWriter",
    "MemoryLinkRepository",
    "MemoryLinkWriter",
    "MemorySummaryBuilder",
    "MemoryTraceExplainer",
    "OutcomeReader",
    "PatternBuilder",
    "PatternConfidenceEvaluator",
    "PatternConfidenceExplainer",
    "PatternReader",
    "PatternRepository",
    "PatternWriter",
    "RetrievalQualityEvaluator",
    "StrategyMemoryReader",
]


from typing import Protocol, Sequence
from ..types import Lesson, LessonQuery, OutcomeFact, Pattern, MemoryRetrieval, StrategyMemoryEntry, LessonDraft, PatternDraft, MemoryLink


class KnowledgeReadPort(Protocol):
    def get(self, lesson_id: str) -> Lesson | None: ...
    def search(self, query: LessonQuery) -> Sequence[Lesson]: ...
    def find_by_subject(self, subject: str) -> Sequence[Pattern]: ...
    def list_outcomes(self, entity_id: str) -> Sequence[OutcomeFact]: ...
    def retrieve(self, retrieval: MemoryRetrieval) -> Sequence[StrategyMemoryEntry]: ...


class KnowledgeWritePort(Protocol):
    def write(self, draft: LessonDraft | PatternDraft | MemoryLink) -> object: ...


__all__.extend(["KnowledgeReadPort", "KnowledgeWritePort"])
