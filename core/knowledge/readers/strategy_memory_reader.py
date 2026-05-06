from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from ..contracts import LessonRepository, PatternRepository, StrategyMemoryReader as StrategyMemoryReaderContract
from ..enums import KnowledgeKind
from ..evaluators.lesson_relevance_evaluator import LessonRelevanceEvaluator
from ..types import MemoryRetrieval, Pattern, StrategyMemoryEntry


@dataclass(frozen=True)
class StrategyMemoryReader(StrategyMemoryReaderContract):
    lesson_repository: LessonRepository
    pattern_repository: PatternRepository
    lesson_relevance_evaluator: LessonRelevanceEvaluator

    def retrieve(self, retrieval: MemoryRetrieval) -> Sequence[StrategyMemoryEntry]:
        lesson_entries = self._build_lesson_entries(retrieval)
        pattern_entries = self._build_pattern_entries(retrieval)
        entries = lesson_entries + pattern_entries
        ranked = sorted(entries, key=self._ranking_score, reverse=True)
        return tuple(ranked[: retrieval.max_items])

    def _build_lesson_entries(self, retrieval: MemoryRetrieval) -> list[StrategyMemoryEntry]:
        entries: list[StrategyMemoryEntry] = []
        for lesson in self.lesson_repository.list_all():
            assessment = self.lesson_relevance_evaluator.evaluate(retrieval, lesson)
            if assessment.relevance_score < retrieval.min_relevance_score:
                continue
            entries.append(
                StrategyMemoryEntry(
                    kind=KnowledgeKind.LESSON,
                    entity_id=lesson.lesson_id,
                    subject=lesson.subject,
                    summary=lesson.title,
                    relevance_score=assessment.relevance_score,
                    freshness_score=self._freshness_score(retrieval.now, lesson.created_at),
                    confidence_score=0.70,
                    support_count=max(len(lesson.evidence_refs), 1),
                    source_refs=(lesson.source_ref,),
                    tags=lesson.tags,
                )
            )
        return entries

    def _build_pattern_entries(self, retrieval: MemoryRetrieval) -> list[StrategyMemoryEntry]:
        entries: list[StrategyMemoryEntry] = []
        for pattern in self.pattern_repository.find_by_subject(retrieval.target_subject):
            relevance_score = self._pattern_relevance_score(retrieval, pattern)
            if relevance_score < retrieval.min_relevance_score:
                continue
            entries.append(
                StrategyMemoryEntry(
                    kind=KnowledgeKind.PATTERN,
                    entity_id=pattern.pattern_id,
                    subject=pattern.subject,
                    summary=pattern.hypothesis,
                    relevance_score=relevance_score,
                    freshness_score=self._freshness_score(retrieval.now, pattern.created_at),
                    confidence_score=pattern.confidence_score,
                    support_count=len(pattern.lesson_ids),
                    source_refs=pattern.lesson_ids,
                    tags=pattern.tags,
                )
            )
        return entries

    @staticmethod
    def _pattern_relevance_score(retrieval: MemoryRetrieval, pattern: Pattern) -> float:
        target_tokens = _tokenize(retrieval.target_subject) | _tokenize(retrieval.task) | set(retrieval.tags.values)
        pattern_tokens = _tokenize(pattern.subject) | _tokenize(pattern.hypothesis) | set(pattern.tags.values)
        matched = target_tokens & pattern_tokens
        denominator = max(len(target_tokens), 1)
        return round(len(matched) / denominator, 4)

    @staticmethod
    def _freshness_score(now: datetime, created_at: datetime) -> float:
        age_days = max((now - created_at).total_seconds() / 86400.0, 0.0)
        if age_days <= 7:
            return 1.0
        if age_days <= 30:
            return 0.8
        if age_days <= 90:
            return 0.6
        if age_days <= 180:
            return 0.4
        return 0.2

    @staticmethod
    def _ranking_score(item: StrategyMemoryEntry) -> float:
        return round(
            item.relevance_score * 0.45 + item.freshness_score * 0.20 + item.confidence_score * 0.20 + min(item.support_count / 3.0, 1.0) * 0.15,
            6,
        )


def _tokenize(text: str) -> set[str]:
    normalized = text.replace("_", " ").replace("-", " ").lower()
    return {part.strip() for part in normalized.split() if part.strip()}
