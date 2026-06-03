from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence

from ..contracts import PatternReader as PatternReaderContract
from ..contracts import PatternRepository
from ..types import Pattern


@dataclass(frozen=True)
class PatternReader(PatternReaderContract):
    repository: PatternRepository

    def get(self, pattern_id: str) -> Pattern | None:
        return self.repository.get(pattern_id)

    def find_by_subject(self, subject: str) -> Sequence[Pattern]:
        return self.repository.find_by_subject(subject)
