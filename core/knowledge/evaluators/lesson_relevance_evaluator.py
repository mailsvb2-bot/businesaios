from __future__ import annotations

from dataclasses import dataclass

from ..types import Lesson, LessonRelevanceAssessment, MemoryRetrieval


@dataclass(frozen=True)
class LessonRelevanceEvaluator:
    def evaluate(self, retrieval: MemoryRetrieval, lesson: Lesson) -> LessonRelevanceAssessment:
        target_tokens = _tokenize(retrieval.target_subject) | _tokenize(retrieval.task) | set(retrieval.tags.values)
        lesson_tokens = _tokenize(lesson.subject) | _tokenize(lesson.title) | _tokenize(lesson.narrative) | set(lesson.tags.values)
        matched = tuple(sorted(target_tokens & lesson_tokens))
        denominator = max(len(target_tokens), 1)
        relevance_score = round(len(matched) / denominator, 4)
        return LessonRelevanceAssessment(
            lesson_id=lesson.lesson_id,
            relevance_score=relevance_score,
            matched_terms=matched,
            reason=f"Matched {len(matched)} of {denominator} target terms.",
        )


def _tokenize(text: str) -> set[str]:
    normalized = text.replace("_", " ").replace("-", " ").lower()
    return {part.strip() for part in normalized.split() if part.strip()}
