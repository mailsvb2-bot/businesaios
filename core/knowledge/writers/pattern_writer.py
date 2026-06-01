from __future__ import annotations

from dataclasses import dataclass

from ..builders.pattern_builder import PatternBuilder
from ..contracts import PatternRepository
from ..contracts import PatternWriter as PatternWriterContract
from ..types import Pattern, PatternDraft


@dataclass(frozen=True)
class PatternWriter(PatternWriterContract):
    builder: PatternBuilder
    repository: PatternRepository

    def write(self, draft: PatternDraft) -> Pattern:
        pattern = self.builder.build(draft)
        return self.repository.save(pattern)
