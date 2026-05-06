from __future__ import annotations

"""Small in-memory safety guards for Telegram ingress.

Goals (pragmatic, not "distributed"):
- prevent accidental update duplication from creating double UX effects
- cap burst processing per chat to avoid queueing lag and "button spam" storms

This intentionally stays in-process and dependency-free.
If you ever run multiple replicas, keep the logic (it still helps locally),
and optionally back it by Redis.
"""

import time
from collections import deque
from dataclasses import dataclass


@dataclass
class RateLimitVerdict:
    allow: bool
    reason: str | None = None


class TTLSeenSet:
    """Remember seen ids for a short TTL."""

    def __init__(self, *, ttl_s: float = 120.0, max_items: int = 50_000):
        self._ttl_s = float(ttl_s)
        self._max_items = int(max_items)
        self._q: deque[tuple[float, str]] = deque()
        self._set: set[str] = set()

    def seen(self, key: str) -> bool:
        now = time.time()
        self._gc(now)
        k = str(key)
        if k in self._set:
            return True
        self._set.add(k)
        self._q.append((now, k))
        # hard cap
        while len(self._q) > self._max_items:
            _, old = self._q.popleft()
            self._set.discard(old)
        return False

    def _gc(self, now: float) -> None:
        ttl = self._ttl_s
        while self._q and (now - self._q[0][0]) > ttl:
            _, old = self._q.popleft()
            self._set.discard(old)


class PerChatTokenBucket:
    """Simple per-chat token bucket.

    - capacity: max burst
    - refill_per_s: tokens per second
    """

    def __init__(self, *, capacity: float = 10.0, refill_per_s: float = 2.0):
        self._cap = float(capacity)
        self._refill = float(refill_per_s)
        self._buckets: dict[str, tuple[float, float]] = {}  # chat_id -> (tokens, ts)

    def allow(self, chat_id: str, *, cost: float = 1.0) -> RateLimitVerdict:
        now = time.time()
        key = str(chat_id)
        tokens, ts = self._buckets.get(key, (self._cap, now))

        # refill
        dt = max(0.0, now - float(ts))
        tokens = min(self._cap, float(tokens) + dt * self._refill)

        if tokens < float(cost):
            self._buckets[key] = (tokens, now)
            return RateLimitVerdict(allow=False, reason="rate_limited")

        tokens -= float(cost)
        self._buckets[key] = (tokens, now)
        return RateLimitVerdict(allow=True)
