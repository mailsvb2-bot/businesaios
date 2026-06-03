from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence

from ..contracts import LessonReader as LessonReaderContract
from ..contracts import LessonRepository
from ..types import Lesson, LessonQuery


@dataclass(frozen=True)
class LessonReader(LessonReaderContract):
    repository: LessonRepository

    def get(self, lesson_id: str) -> Lesson | None:
        return self.repository.get(lesson_id)

    def search(self, query: LessonQuery) -> Sequence[Lesson]:
        return self.repository.find(query)
