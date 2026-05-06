from __future__ import annotations

from dataclasses import dataclass

from ..enums import ConfidenceLevel
from ..types import Pattern, PatternConfidenceAssessment


@dataclass(frozen=True)
class PatternConfidenceEvaluator:
    def evaluate(self, pattern: Pattern) -> PatternConfidenceAssessment:
        score = pattern.confidence_score
        support_count = len(pattern.lesson_ids)
        if score >= 0.80 and support_count >= 2:
            level = ConfidenceLevel.HIGH
            reason = "Pattern is supported by multiple lessons and strong confidence."
        elif score >= 0.55 and support_count >= 1:
            level = ConfidenceLevel.MEDIUM
            reason = "Pattern is usable with caution."
        else:
            level = ConfidenceLevel.LOW
            reason = "Pattern is weak or under-supported and should not drive strict reuse."
        return PatternConfidenceAssessment(
            pattern_id=pattern.pattern_id,
            confidence_score=score,
            confidence_level=level,
            support_count=support_count,
            reason=reason,
        )
