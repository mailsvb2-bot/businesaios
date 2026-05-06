from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class OverrideApplied:
    override_id: str
    review_id: str
    actor_id: str
    applied_at: datetime
    reason: str
