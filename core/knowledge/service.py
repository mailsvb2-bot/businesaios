from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .contracts import (
    BusinessCaseBuilder,
    EventPublisher,
    KnowledgeGuard,
    LessonReader,
    LessonRelevanceEvaluator,
    LessonUsageExplainer,
    LessonWriter,
    MemoryLinkWriter,
    MemorySummaryBuilder,
    MemoryTraceExplainer,
    PatternConfidenceEvaluator,
    PatternConfidenceExplainer,
    PatternReader,
    PatternWriter,
    StrategyMemoryReader,
)
from .errors import KnowledgeError, KnowledgeNotFoundError
from .events.lesson_recorded import LessonRecorded
from .events.memory_reuse_blocked import MemoryReuseBlocked
from .events.pattern_materialized import PatternMaterialized
from .types import (
    BusinessCase,
    Lesson,
    LessonDraft,
    MemoryLink,
    MemoryRetrieval,
    MemorySummary,
    Pattern,
    PatternDraft,
    StrategyMemoryEntry,
)


@dataclass(frozen=True)
class KnowledgeService:
    """Legacy compatibility wrapper used by a few boot tests.

    It intentionally stays thin and does not introduce a second knowledge brain.
    """

    event_store: Any
    readers: Mapping[str, Any]
    writers: Mapping[str, Any]


@dataclass(frozen=True)
class KnowledgeCommandService:
    lesson_writer: LessonWriter
    pattern_writer: PatternWriter
    memory_link_writer: MemoryLinkWriter
    event_publisher: EventPublisher

    def record_lesson(self, draft: LessonDraft) -> Lesson:
        lesson = self.lesson_writer.write(draft)
        self.event_publisher.publish(
            LessonRecorded(
                lesson_id=lesson.lesson_id,
                subject=lesson.subject,
                source_ref=lesson.source_ref,
                recorded_at=lesson.created_at,
            )
        )
        return lesson

    def materialize_pattern(self, draft: PatternDraft) -> Pattern:
        pattern = self.pattern_writer.write(draft)
        self.event_publisher.publish(
            PatternMaterialized(
                pattern_id=pattern.pattern_id,
                subject=pattern.subject,
                lesson_ids=pattern.lesson_ids,
                confidence_score=pattern.confidence_score,
                materialized_at=pattern.created_at,
            )
        )
        return pattern

    def link_memory(self, link: MemoryLink) -> MemoryLink:
        return self.memory_link_writer.write(link)


@dataclass(frozen=True)
class KnowledgeQueryService:
    strategy_memory_reader: StrategyMemoryReader
    knowledge_guard: KnowledgeGuard
    memory_summary_builder: MemorySummaryBuilder
    lesson_reader: LessonReader
    pattern_reader: PatternReader
    business_case_builder: BusinessCaseBuilder
    event_publisher: EventPublisher

    def retrieve_memory(self, retrieval: MemoryRetrieval) -> MemorySummary:
        entries = self._retrieve_safe_entries(retrieval, publish_block_event=True)
        return self.memory_summary_builder.build(retrieval, entries)

    def build_business_case(self, lesson_id: str) -> BusinessCase:
        lesson = self.lesson_reader.get(lesson_id)
        if lesson is None:
            raise KnowledgeNotFoundError(f"Lesson not found: {lesson_id}")

        patterns = self.pattern_reader.find_by_subject(lesson.subject)
        linked_patterns = tuple(pattern for pattern in patterns if lesson.lesson_id in pattern.lesson_ids)
        return self.business_case_builder.build(lesson, linked_patterns)

    def _retrieve_safe_entries(
        self,
        retrieval: MemoryRetrieval,
        *,
        publish_block_event: bool,
    ) -> Sequence[StrategyMemoryEntry]:
        entries = self.strategy_memory_reader.retrieve(retrieval)

        try:
            self.knowledge_guard.ensure_reuse_is_safe(retrieval, entries)
        except KnowledgeError as exc:
            if publish_block_event:
                self.event_publisher.publish(
                    MemoryReuseBlocked(
                        target_subject=retrieval.target_subject,
                        task=retrieval.task,
                        reason=str(exc),
                        blocked_at=retrieval.now,
                    )
                )
            raise

        return entries


@dataclass(frozen=True)
class KnowledgeExplainService:
    query_service: KnowledgeQueryService
    lesson_reader: LessonReader
    pattern_reader: PatternReader
    lesson_relevance_evaluator: LessonRelevanceEvaluator
    pattern_confidence_evaluator: PatternConfidenceEvaluator
    memory_trace_explainer: MemoryTraceExplainer
    lesson_usage_explainer: LessonUsageExplainer
    pattern_confidence_explainer: PatternConfidenceExplainer

    def explain_retrieval(self, retrieval: MemoryRetrieval) -> str:
        summary = self.query_service.retrieve_memory(retrieval)
        return self.memory_trace_explainer.explain(summary)

    def explain_lesson_usage(self, lesson_id: str, retrieval: MemoryRetrieval) -> str:
        lesson = self.lesson_reader.get(lesson_id)
        if lesson is None:
            raise KnowledgeNotFoundError(f"Lesson not found: {lesson_id}")

        assessment = self.lesson_relevance_evaluator.evaluate(retrieval, lesson)
        return self.lesson_usage_explainer.explain(lesson, assessment)

    def explain_pattern_confidence(self, pattern_id: str) -> str:
        pattern = self.pattern_reader.get(pattern_id)
        if pattern is None:
            raise KnowledgeNotFoundError(f"Pattern not found: {pattern_id}")

        assessment = self.pattern_confidence_evaluator.evaluate(pattern)
        return self.pattern_confidence_explainer.explain(pattern, assessment)
