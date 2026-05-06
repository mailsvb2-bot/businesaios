from __future__ import annotations

"""Compatibility shim for knowledge contract surfaces.

Canonical owner: core.knowledge.contracts package.
This module preserves historical imports without keeping a second copy of
protocol definitions.
"""

from .contracts import (
    BusinessCaseBuilder,
    EventPublisher,
    KnowledgeGuard,
    KnowledgeReadPort,
    KnowledgeWritePort,
    LessonBuilder,
    LessonReader,
    LessonRelevanceEvaluator,
    LessonRepository,
    LessonUsageExplainer,
    LessonWriter,
    MemoryLinkRepository,
    MemoryLinkWriter,
    MemorySummaryBuilder,
    MemoryTraceExplainer,
    OutcomeReader,
    PatternBuilder,
    PatternConfidenceEvaluator,
    PatternConfidenceExplainer,
    PatternReader,
    PatternRepository,
    PatternWriter,
    RetrievalQualityEvaluator,
    StrategyMemoryReader,
)

CANON_COMPAT_SHIM = True

__all__ = [
    "BusinessCaseBuilder",
    "CANON_COMPAT_SHIM",
    "EventPublisher",
    "KnowledgeGuard",
    "KnowledgeReadPort",
    "KnowledgeWritePort",
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
