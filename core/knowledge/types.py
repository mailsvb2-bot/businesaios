from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping, Sequence

from config.world_model_defaults import DEFAULT_WORLD_MODEL_DEFAULTS

from .enums import (
    ConfidenceLevel,
    KnowledgeKind,
    LessonStatus,
    OutcomePolarity,
    ReuseSafety,
    SourceKind,
)


@dataclass(frozen=True)
class TagSet:
    values: tuple[str, ...]

    @classmethod
    def from_iterable(cls, values: Sequence[str]) -> "TagSet":
        normalized: list[str] = []
        seen: set[str] = set()
        for raw_value in values:
            value = str(raw_value).strip().lower()
            if not value or value in seen:
                continue
            seen.add(value)
            normalized.append(value)
        return cls(values=tuple(normalized))

    def contains(self, value: str) -> bool:
        return value.strip().lower() in set(self.values)

    def overlaps(self, values: Sequence[str]) -> bool:
        other = {str(value).strip().lower() for value in values if str(value).strip()}
        return bool(set(self.values) & other)


@dataclass(frozen=True)
class LessonDraft:
    subject: str
    title: str
    narrative: str
    source_kind: SourceKind
    source_ref: str
    tags: TagSet
    observed_at: datetime
    created_by: str
    evidence_refs: tuple[str, ...] = ()
    outcome_refs: tuple[str, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Lesson:
    lesson_id: str
    subject: str
    title: str
    narrative: str
    source_kind: SourceKind
    source_ref: str
    tags: TagSet
    observed_at: datetime
    created_at: datetime
    created_by: str
    status: LessonStatus
    evidence_refs: tuple[str, ...]
    outcome_refs: tuple[str, ...]
    metadata: Mapping[str, str]


@dataclass(frozen=True)
class PatternDraft:
    subject: str
    hypothesis: str
    lesson_ids: tuple[str, ...]
    signal_count: int
    contradictory_signal_count: int
    tags: TagSet
    created_by: str
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Pattern:
    pattern_id: str
    subject: str
    hypothesis: str
    lesson_ids: tuple[str, ...]
    signal_count: int
    contradictory_signal_count: int
    confidence_level: ConfidenceLevel
    confidence_score: float
    tags: TagSet
    created_at: datetime
    created_by: str
    metadata: Mapping[str, str]


@dataclass(frozen=True)
class MemoryLink:
    link_id: str
    source_kind: KnowledgeKind
    source_id: str
    target_kind: KnowledgeKind
    target_id: str
    rationale: str
    created_at: datetime
    created_by: str


@dataclass(frozen=True)
class LessonQuery:
    subject: str | None = None
    tags: TagSet | None = None
    free_text: str | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None
    limit: int = DEFAULT_WORLD_MODEL_DEFAULTS.lesson_query_limit


@dataclass(frozen=True)
class OutcomeFact:
    outcome_id: str
    entity_id: str
    summary: str
    polarity: OutcomePolarity
    measured_at: datetime
    metrics: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class StrategyMemoryEntry:
    kind: KnowledgeKind
    entity_id: str
    subject: str
    summary: str
    relevance_score: float
    freshness_score: float
    confidence_score: float
    support_count: int
    source_refs: tuple[str, ...] = ()
    tags: TagSet = field(default_factory=lambda: TagSet(values=()))


@dataclass(frozen=True)
class MemoryRetrieval:
    target_subject: str
    task: str
    tags: TagSet
    now: datetime
    max_items: int = DEFAULT_WORLD_MODEL_DEFAULTS.memory_retrieval_max_items
    min_relevance_score: float = DEFAULT_WORLD_MODEL_DEFAULTS.memory_relevance_floor
    min_freshness_score: float = DEFAULT_WORLD_MODEL_DEFAULTS.memory_freshness_floor
    min_support_count: int = DEFAULT_WORLD_MODEL_DEFAULTS.memory_min_support_count
    strict_mode: bool = True


@dataclass(frozen=True)
class MemorySummary:
    retrieval: MemoryRetrieval
    entries: tuple[StrategyMemoryEntry, ...]
    summary_text: str
    coverage_score: float
    quality_score: float
    safety: ReuseSafety


@dataclass(frozen=True)
class BusinessCase:
    subject: str
    lesson_id: str
    pattern_ids: tuple[str, ...]
    rationale: str
    expected_benefit: str
    key_risks: tuple[str, ...]


@dataclass(frozen=True)
class LessonRelevanceAssessment:
    lesson_id: str
    relevance_score: float
    matched_terms: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class PatternConfidenceAssessment:
    pattern_id: str
    confidence_score: float
    confidence_level: ConfidenceLevel
    support_count: int
    reason: str


@dataclass(frozen=True)
class RetrievalQualityAssessment:
    item_count: int
    quality_score: float
    coverage_score: float
    safety: ReuseSafety
    reason: str
