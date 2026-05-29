from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ..types import Pattern


@dataclass(frozen=True)
class PatternIndexProjection:
    pattern_id: str
    subject: str
    hypothesis: str
    confidence_score: float
    support_count: int

    @classmethod
    def from_pattern(cls, pattern: Pattern) -> PatternIndexProjection:
        return cls(
            pattern_id=pattern.pattern_id,
            subject=pattern.subject,
            hypothesis=pattern.hypothesis,
            confidence_score=pattern.confidence_score,
            support_count=len(pattern.lesson_ids),
        )

    @classmethod
    def build_many(cls, patterns: Sequence[Pattern]) -> tuple[PatternIndexProjection, ...]:
        return tuple(cls.from_pattern(pattern) for pattern in patterns)
