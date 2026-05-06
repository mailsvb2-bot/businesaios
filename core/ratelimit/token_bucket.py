from __future__ import annotations

import time
import asyncio
from dataclasses import dataclass
from typing import Protocol, Optional, Dict, Tuple

from config.token_bucket_policy import (
    DEFAULT_TOKEN_BUCKET_POLICY_DEFAULTS,
    TokenBucketPolicyDefaults,
)
from core.tenancy.scope import TenantId


@dataclass(frozen=True)
class RateLimitKey:
    tenant_id: TenantId
    subject: str  # user_id / ip / api_key
    bucket: str   # endpoint name, e.g. "payments.create"

    def normalized(self) -> str:
        t = str(self.tenant_id)
        defaults = DEFAULT_TOKEN_BUCKET_POLICY_DEFAULTS
        s = (self.subject or "").strip() or defaults.anonymous_subject
        b = (self.bucket or "").strip() or defaults.default_bucket
        return f"{t}:{s}:{b}"


@dataclass(frozen=True)
class RateLimitPolicy:
    capacity: int
    refill_per_sec: float  # tokens per second


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    remaining: int
    retry_after_ms: int = 0


class RateLimitStore(Protocol):
    def get_state(self, *, key: str) -> Optional[Tuple[float, float]]: ...

    def set_state(self, *, key: str, tokens: float, updated_at_s: float) -> None: ...


class MemoryRateLimitStore:
    def __init__(self):
        self._m: Dict[str, Tuple[float, float]] = {}

    def get_state(self, *, key: str) -> Optional[Tuple[float, float]]:
        return self._m.get(key)

    def set_state(self, *, key: str, tokens: float, updated_at_s: float) -> None:
        self._m[key] = (float(tokens), float(updated_at_s))


class TokenBucketLimiter:
    """Deterministic token bucket limiter."""

    def __init__(self, store: RateLimitStore):
        self._store = store

    def check(self, *, key: RateLimitKey, policy: RateLimitPolicy, cost: int = 1) -> RateLimitDecision:
        k = key.normalized()
        now_s = time.time()
        defaults = DEFAULT_TOKEN_BUCKET_POLICY_DEFAULTS
        cap = max(int(defaults.min_capacity), int(policy.capacity))
        refill = max(float(defaults.zero_tokens), float(policy.refill_per_sec))
        cost = max(int(defaults.min_cost), int(cost))

        st = self._store.get_state(key=k)
        if st is None:
            tokens = float(cap)
            last = now_s
        else:
            tokens, last = st

        dt = max(float(defaults.zero_tokens), now_s - float(last))
        tokens = min(float(cap), float(tokens) + dt * refill)

        if tokens >= cost:
            tokens -= cost
            self._store.set_state(key=k, tokens=tokens, updated_at_s=now_s)
            return RateLimitDecision(allowed=True, remaining=int(tokens))

        need = float(cost) - float(tokens)
        retry_s = (need / refill) if refill > 0 else float(defaults.fallback_retry_seconds)
        retry_ms = int(max(float(defaults.min_retry_seconds), float(retry_s)) * 1000)
        self._store.set_state(key=k, tokens=tokens, updated_at_s=now_s)
        return RateLimitDecision(allowed=False, remaining=int(tokens), retry_after_ms=retry_ms)


# ---------------------------------------------------------------------------
# Convenience wrappers (transport-facing)
# ---------------------------------------------------------------------------


class SyncTokenBucket:
    """Tiny token bucket with a stable single key.

    This is intentionally a convenience layer over TokenBucketLimiter to avoid
    duplicated ad-hoc token-bucket implementations in transport code.
    """

    def __init__(
        self,
        *,
        capacity: int,
        refill_per_s: float,
        tenant_id: 'TenantId | str' = TenantId(DEFAULT_TOKEN_BUCKET_POLICY_DEFAULTS.transport_tenant_id),
        subject: str = DEFAULT_TOKEN_BUCKET_POLICY_DEFAULTS.transport_subject,
        bucket: str = DEFAULT_TOKEN_BUCKET_POLICY_DEFAULTS.default_bucket,
        store: 'RateLimitStore | None' = None,
    ) -> None:
        self._store = store or MemoryRateLimitStore()
        self._limiter = TokenBucketLimiter(self._store)
        self._key = RateLimitKey(tenant_id=TenantId(str(tenant_id)), subject=str(subject), bucket=str(bucket))
        self._policy = RateLimitPolicy(capacity=int(capacity), refill_per_sec=float(refill_per_s))

    def try_take(self, tokens: float = DEFAULT_TOKEN_BUCKET_POLICY_DEFAULTS.default_take_tokens) -> bool:
        dec = self._limiter.check(key=self._key, policy=self._policy, cost=max(1, int(tokens)))
        return bool(dec.allowed)

    def check(self, tokens: int = 1) -> 'RateLimitDecision':
        return self._limiter.check(key=self._key, policy=self._policy, cost=max(1, int(tokens)))


class AsyncTokenBucket:
    """Async token bucket wrapper.

    acquire() sleeps until allowed. Designed for lightweight asyncio transports.
    """

    def __init__(
        self,
        *,
        rps: float,
        burst: int,
        tenant_id: 'TenantId | str' = TenantId(DEFAULT_TOKEN_BUCKET_POLICY_DEFAULTS.transport_tenant_id),
        subject: str = DEFAULT_TOKEN_BUCKET_POLICY_DEFAULTS.transport_subject,
        bucket: str = DEFAULT_TOKEN_BUCKET_POLICY_DEFAULTS.default_bucket,
        store: 'RateLimitStore | None' = None,
    ) -> None:
        self._sync = SyncTokenBucket(
            capacity=int(burst),
            refill_per_s=float(rps),
            tenant_id=tenant_id,
            subject=subject,
            bucket=bucket,
            store=store,
        )

    def take(self, n: float = DEFAULT_TOKEN_BUCKET_POLICY_DEFAULTS.default_take_tokens) -> bool:
        return self._sync.try_take(float(n))

    async def acquire(self, n: float = DEFAULT_TOKEN_BUCKET_POLICY_DEFAULTS.default_take_tokens) -> None:
        while True:
            d = self._sync.check(tokens=max(1, int(n)))
            if d.allowed:
                return
            await asyncio.sleep(max(float(DEFAULT_TOKEN_BUCKET_POLICY_DEFAULTS.async_min_sleep_s), float(d.retry_after_ms) / int(DEFAULT_TOKEN_BUCKET_POLICY_DEFAULTS.milliseconds_per_second)))
