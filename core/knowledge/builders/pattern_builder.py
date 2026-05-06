from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from ..enums import ConfidenceLevel
from ..errors import KnowledgeValidationError
from ..ids import new_pattern_id
from ..types import Pattern, PatternDraft


@dataclass(frozen=True)
class PatternBuilder:
    def build(self, draft: PatternDraft) -> Pattern:
        subject = draft.subject.strip().lower()
        hypothesis = draft.hypothesis.strip()
        created_by = draft.created_by.strip()
        lesson_ids = tuple(
            dict.fromkeys(
                lesson_id.strip()
                for lesson_id in draft.lesson_ids
                if lesson_id and lesson_id.strip()
            )
        )

        if not subject:
            raise KnowledgeValidationError("Pattern subject is required.")
        if not hypothesis:
            raise KnowledgeValidationError("Pattern hypothesis is required.")
        if not created_by:
            raise KnowledgeValidationError("Pattern created_by is required.")
        if not lesson_ids:
            raise KnowledgeValidationError("Pattern must reference at least one lesson.")
        if draft.signal_count < 0:
            raise KnowledgeValidationError("Pattern signal_count cannot be negative.")
        if draft.contradictory_signal_count < 0:
            raise KnowledgeValidationError("Pattern contradictory_signal_count cannot be negative.")
        if draft.signal_count == 0:
            raise KnowledgeValidationError("Pattern signal_count must be greater than zero.")
        if draft.contradictory_signal_count > draft.signal_count * 10:
            raise KnowledgeValidationError("Pattern contradictory_signal_count is implausibly high.")

        confidence_score = self._score(
            signal_count=draft.signal_count,
            contradictory_signal_count=draft.contradictory_signal_count,
        )
        confidence_level = self._level(confidence_score)

        return Pattern(
            pattern_id=new_pattern_id(),
            subject=subject,
            hypothesis=hypothesis,
            lesson_ids=lesson_ids,
            signal_count=draft.signal_count,
            contradictory_signal_count=draft.contradictory_signal_count,
            confidence_level=confidence_level,
            confidence_score=confidence_score,
            tags=draft.tags,
            created_at=datetime.now(tz=timezone.utc),
            created_by=created_by,
            metadata=dict(draft.metadata),
        )

    @staticmethod
    def _score(signal_count: int, contradictory_signal_count: int) -> float:
        total = signal_count + contradictory_signal_count
        if total <= 0:
            return 0.0
        consistency_ratio = signal_count / total
        support_bonus = min(signal_count / 20.0, 0.20)
        score = consistency_ratio + support_bonus
        return round(min(score, 1.0), 4)

    @staticmethod
    def _level(confidence_score: float) -> ConfidenceLevel:
        if confidence_score >= 0.80:
            return ConfidenceLevel.HIGH
        if confidence_score >= 0.55:
            return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.LOW
