from __future__ import annotations

from datetime import datetime, timedelta


def next_retry_time(now: datetime, retry_cooldown_level: int) -> datetime:
    level_to_delay_hours = {
        0: 0,
        1: 12,
        2: 24,
        3: 72,
    }
    delay = level_to_delay_hours.get(retry_cooldown_level, 24)
    return now + timedelta(hours=delay)
