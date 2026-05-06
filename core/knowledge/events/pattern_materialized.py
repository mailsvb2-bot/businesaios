from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class PatternMaterialized:
    pattern_id: str
    subject: str
    lesson_ids: tuple[str, ...]
    confidence_score: float
    materialized_at: datetime
