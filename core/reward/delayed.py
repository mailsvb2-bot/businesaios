from __future__ import annotations

from datetime import timedelta

from config.env_flags import env_str


def _delay() -> timedelta:
    env = env_str("ENV", "dev").lower()
    if env in {"prod", "production"}:
        return timedelta(hours=24)
    # Dev/test: no delay unless explicitly requested.
    h = env_str("REWARD_DELAY_HOURS", "") or None
    if h is None:
        return timedelta(hours=0)
    try:
        return timedelta(hours=float(h))
    except Exception:
        return timedelta(hours=0)


def eligible(*, event_time_ms: int, now_ms: int) -> bool:
    d = _delay()
    return int(now_ms) - int(event_time_ms) >= int(d.total_seconds() * 1000)
