from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from threading import RLock

from core.tenancy.normalization import require_tenant_id
from runtime.queue.job_contract import normalize_now, utc_now

CANON_RUNTIME_QUEUE_RATE_LIMIT_GUARD = True


@dataclass(frozen=True)
class RateLimitVerdict:
    allowed: bool
    reason: str
    retry_after_seconds: int = 0


@dataclass
class _WindowState:
    used: int = 0
    resets_at: datetime = field(default_factory=utc_now)


class RateLimitGuard:
    """Simple fixed-window limiter for queue admission.

    Scope is tenant + queue. This is operational protection, not policy logic.
    """

    def __init__(self, *, limit_per_minute: int = 300) -> None:
        self._limit_per_minute = max(1, int(limit_per_minute))
        self._windows: dict[tuple[str, str], _WindowState] = {}
        self._lock = RLock()

    def evaluate(self, *, tenant_id: str, queue_name: str, units: int = 1, now: datetime | None = None) -> RateLimitVerdict:
        moment = normalize_now(now)
        tid = require_tenant_id(tenant_id)
        qn = str(queue_name).strip()
        if not qn:
            raise ValueError("queue_name is required")
        cost = max(1, int(units))

        with self._lock:
            key = (tid, qn)
            window = self._windows.get(key)
            if window is None or moment >= window.resets_at:
                window = _WindowState(used=0, resets_at=moment + timedelta(minutes=1))
                self._windows[key] = window

            if int(window.used) + cost > self._limit_per_minute:
                retry_after = max(1, int((window.resets_at - moment).total_seconds()))
                return RateLimitVerdict(False, "queue_rate_limited", retry_after)

            window.used += cost
            return RateLimitVerdict(True, "allowed", 0)


__all__ = [
    "CANON_RUNTIME_QUEUE_RATE_LIMIT_GUARD",
    "RateLimitGuard",
    "RateLimitVerdict",
]
