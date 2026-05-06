"""Deprecated network rate limiting helpers.

Layering rule: platform_layer must not import from core.

This file intentionally carries a tiny token bucket implementation for
backwards compatibility with older network adapters.

Canonical runtime rate limiting lives in core.*, but transports that live in
platform_layer must not depend on it.
"""

from __future__ import annotations

import asyncio
import threading
import time


class TokenBucket:
    """Async token bucket (lightweight, best-effort)."""

    def __init__(self, *, rps: float, burst: int) -> None:
        self._cap = float(max(1, int(burst)))
        self._refill = float(max(0.001, float(rps)))
        self._tokens = float(self._cap)
        self._ts = time.monotonic()
        self._lock = threading.Lock()

    def take(self, n: float = 1.0) -> bool:
        need = float(max(0.001, float(n)))
        with self._lock:
            now = time.monotonic()
            dt = max(0.0, now - self._ts)
            self._ts = now
            self._tokens = min(self._cap, self._tokens + dt * self._refill)
            if self._tokens >= need:
                self._tokens -= need
                return True
            return False

    async def acquire(self, n: float = 1.0) -> None:
        while not self.take(float(n)):
            await asyncio.sleep(0.02)
