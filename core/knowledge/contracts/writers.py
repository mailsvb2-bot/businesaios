"""Writer protocols for knowledge domain."""
from __future__ import annotations

from typing import Protocol

from ..types import (
    Lesson,
    LessonDraft,
    MemoryLink,
    Pattern,
    PatternDraft,
)

__all__ = [
    "LessonWriter",
    "PatternWriter",
    "MemoryLinkWriter",
]


class LessonWriter(Protocol):
    def write(self, draft: LessonDraft) -> Lesson: ...


class PatternWriter(Protocol):
    def write(self, draft: PatternDraft) -> Pattern: ...


class MemoryLinkWriter(Protocol):
    def write(self, link: MemoryLink) -> MemoryLink: ...
