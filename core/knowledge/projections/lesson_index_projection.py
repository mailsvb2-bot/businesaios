from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ..types import Lesson


@dataclass(frozen=True)
class LessonIndexProjection:
    lesson_id: str
    subject: str
    title: str
    tags: tuple[str, ...]

    @classmethod
    def from_lesson(cls, lesson: Lesson) -> "LessonIndexProjection":
        return cls(lesson_id=lesson.lesson_id, subject=lesson.subject, title=lesson.title, tags=lesson.tags.values)

    @classmethod
    def build_many(cls, lessons: Sequence[Lesson]) -> tuple["LessonIndexProjection", ...]:
        return tuple(cls.from_lesson(lesson) for lesson in lessons)
