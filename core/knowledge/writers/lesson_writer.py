from __future__ import annotations

from dataclasses import dataclass

from ..builders.lesson_builder import LessonBuilder
from ..contracts import LessonRepository
from ..contracts import LessonWriter as LessonWriterContract
from ..types import Lesson, LessonDraft


@dataclass(frozen=True)
class LessonWriter(LessonWriterContract):
    builder: LessonBuilder
    repository: LessonRepository

    def write(self, draft: LessonDraft) -> Lesson:
        lesson = self.builder.build(draft)
        return self.repository.save(lesson)
