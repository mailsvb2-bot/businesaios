from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class CacheWindow:
    value: Dict[str, Any]
    latest_event_ts: int
    computed_at_ms: int


def is_cache_fresh(*, cached: Optional[CacheWindow], latest_ts: int, now_ms: int, ttl_ms: int) -> bool:
    return bool(cached and cached.latest_event_ts == latest_ts and (now_ms - cached.computed_at_ms) < ttl_ms)
