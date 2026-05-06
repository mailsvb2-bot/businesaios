from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

SprintStatus = Literal["not_started", "active", "completed", "paused", "failed"]


@dataclass(frozen=True)
class RevenueSprintConfig:
    days: int = 7
    daily_send_hour_local: int = 10
    autopilot_enabled: bool = True
    seed_offer_catalog: bool = True
    seed_telemetry: bool = True


@dataclass
class RevenueSprintState:
    status: SprintStatus = "not_started"
    started_at_utc: Optional[datetime] = None
    ends_at_utc: Optional[datetime] = None
    day_index: int = 0

    def start(self, *, now_utc: datetime, days: int) -> "RevenueSprintState":
        now_utc = now_utc.astimezone(timezone.utc)
        self.status = "active"
        self.started_at_utc = now_utc
        self.ends_at_utc = now_utc + timedelta(days=int(days))
        self.day_index = 0
        return self

    def is_active(self, *, now_utc: datetime) -> bool:
        if self.status != "active" or not self.ends_at_utc:
            return False
        return now_utc.astimezone(timezone.utc) < self.ends_at_utc
