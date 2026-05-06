from __future__ import annotations

from dataclasses import dataclass

from ..types import Pattern, PatternConfidenceAssessment


@dataclass(frozen=True)
class PatternConfidenceExplainer:
    def explain(self, pattern: Pattern, assessment: PatternConfidenceAssessment) -> str:
        return (
            f"Pattern confidence explanation:\n"
            f"- pattern_id: {pattern.pattern_id}\n"
            f"- subject: {pattern.subject}\n"
            f"- confidence_score: {assessment.confidence_score:.2f}\n"
            f"- confidence_level: {assessment.confidence_level.value}\n"
            f"- support_count: {assessment.support_count}\n"
            f"- reason: {assessment.reason}"
        )
