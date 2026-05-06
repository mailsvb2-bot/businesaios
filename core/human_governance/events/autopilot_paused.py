from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class AutopilotPaused:
    review_id: str
    actor_id: str
    paused_at: datetime
    reason: str
