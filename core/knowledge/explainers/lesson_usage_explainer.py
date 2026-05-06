from __future__ import annotations

from dataclasses import dataclass

from ..types import Lesson, LessonRelevanceAssessment


@dataclass(frozen=True)
class LessonUsageExplainer:
    def explain(self, lesson: Lesson, assessment: LessonRelevanceAssessment) -> str:
        terms = ", ".join(assessment.matched_terms) if assessment.matched_terms else "none"
        return (
            f"Lesson usage explanation:\n"
            f"- lesson_id: {lesson.lesson_id}\n"
            f"- subject: {lesson.subject}\n"
            f"- title: {lesson.title}\n"
            f"- relevance_score: {assessment.relevance_score:.2f}\n"
            f"- matched_terms: {terms}\n"
            f"- reason: {assessment.reason}"
        )
