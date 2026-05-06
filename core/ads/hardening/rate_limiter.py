"""Per-tenant ads API rate limiter.

Simple token-bucket limiter scoped by tenant_id.
Prevents a single tenant from exhausting platform API quotas.

Patch 10.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from config.ads_hardening_policy import (
    DEFAULT_ADS_RATE_LIMITER_POLICY,
    AdsRateLimiterPolicy,
)


@dataclass
class _Bucket:
    tokens: float
    last_refill: float
    capacity: float
    rate: float  # tokens per second

    def try_consume(self, n: float = DEFAULT_ADS_RATE_LIMITER_POLICY.default_consume_tokens) -> bool:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_refill = now
        if self.tokens >= n:
            self.tokens -= n
            return True
        return False


class AdsRateLimiter:
    """Per-tenant token-bucket rate limiter for ads API calls."""

    def __init__(
        self,
        *,
        rate: float | None = None,
        burst: int | None = None,
        policy: AdsRateLimiterPolicy = DEFAULT_ADS_RATE_LIMITER_POLICY,
    ) -> None:
        self._policy = policy
        self._rate = float(policy.rate if rate is None else rate)
        self._burst = int(policy.burst if burst is None else burst)
        self._buckets: dict[str, _Bucket] = {}

    def allow(self, tenant_id: str) -> bool:
        if tenant_id not in self._buckets:
            self._buckets[tenant_id] = _Bucket(
                tokens=float(self._burst),
                last_refill=time.monotonic(),
                capacity=float(self._burst),
                rate=self._rate,
            )
        return self._buckets[tenant_id].try_consume()

    def assert_allowed(self, tenant_id: str) -> None:
        if not self.allow(tenant_id):
            raise RuntimeError(f"ADS_RATE_LIMITED: tenant={tenant_id}")
