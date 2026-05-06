from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class MemoryReuseBlocked:
    target_subject: str
    task: str
    reason: str
    blocked_at: datetime
