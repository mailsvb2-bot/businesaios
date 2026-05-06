from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class LessonRecorded:
    lesson_id: str
    subject: str
    source_ref: str
    recorded_at: datetime
