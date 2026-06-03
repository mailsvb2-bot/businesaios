from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence

from ..types import BusinessCase, Lesson, Pattern


@dataclass(frozen=True)
class BusinessCaseBuilder:
    def build(self, lesson: Lesson, linked_patterns: Sequence[Pattern]) -> BusinessCase:
        pattern_ids = tuple(pattern.pattern_id for pattern in linked_patterns)
        risks: list[str] = []
        if not linked_patterns:
            risks.append("No linked patterns support this lesson yet.")
        for pattern in linked_patterns:
            if pattern.confidence_score < 0.55:
                risks.append(f"Pattern {pattern.pattern_id} has weak confidence.")
            if len(pattern.lesson_ids) < 1:
                risks.append(f"Pattern {pattern.pattern_id} has no supporting lessons.")
        if not risks:
            risks.append("No major knowledge integrity risks detected.")
        rationale = (
            f"Lesson '{lesson.title}' captures reusable operational knowledge for subject '{lesson.subject}'."
        )
        expected_benefit = (
            "Faster evidence reuse, lower repetition of prior mistakes, and stronger institutional memory continuity."
        )
        return BusinessCase(
            subject=lesson.subject,
            lesson_id=lesson.lesson_id,
            pattern_ids=pattern_ids,
            rationale=rationale,
            expected_benefit=expected_benefit,
            key_risks=tuple(risks),
        )
