from __future__ import annotations

"""Runtime action rate limiting (canonical enforcement).

Goal:
- apply per-tenant and per-user limits *before* any side-effect
- limits are defined in runtime.boot.actions_registry.ActionSpecV1

This module is intentionally small and deterministic.
"""

from dataclasses import dataclass

from runtime.ratelimit import (
    MemoryRateLimitStore,
    RateLimitKey,
    RateLimitPolicy,
    TokenBucketLimiter,
)
from runtime.tenancy import TenantId

from runtime.boot.actions_registry import ActionSpecV1


@dataclass(frozen=True)
class RuntimeLimitVerdict:
    allowed: bool
    retry_after_ms: int = 0
    reason: str = ""


class RuntimeActionRateLimiter:
    """Enforces action limits based on ActionSpecV1."""

    def __init__(self, store=None) -> None:
        self._store = store or MemoryRateLimitStore()
        self._limiter = TokenBucketLimiter(self._store)

    def _policy(self, per_min: int) -> RateLimitPolicy:
        per_min = max(1, int(per_min))
        return RateLimitPolicy(capacity=per_min, refill_per_sec=float(per_min) / 60.0)

    def check(
        self,
        *,
        spec: ActionSpecV1,
        tenant_id: str,
        user_id: str,
        cost: int = 1,
    ) -> RuntimeLimitVerdict:
        kind = str(spec.limits.kind)
        action = str(spec.name)

        # Tenant bucket
        t_key = RateLimitKey(tenant_id=TenantId(str(tenant_id)), subject="__tenant__", bucket=f"{kind}:{action}")
        t_dec = self._limiter.check(key=t_key, policy=self._policy(spec.limits.per_tenant_per_min), cost=cost)
        if not t_dec.allowed:
            return RuntimeLimitVerdict(allowed=False, retry_after_ms=t_dec.retry_after_ms, reason="TENANT_RATE_LIMITED")

        # User bucket
        u_key = RateLimitKey(tenant_id=TenantId(str(tenant_id)), subject=str(user_id), bucket=f"{kind}:{action}")
        u_dec = self._limiter.check(key=u_key, policy=self._policy(spec.limits.per_user_per_min), cost=cost)
        if not u_dec.allowed:
            return RuntimeLimitVerdict(allowed=False, retry_after_ms=u_dec.retry_after_ms, reason="USER_RATE_LIMITED")

        return RuntimeLimitVerdict(allowed=True)

    def assert_allowed(self, *, spec: ActionSpecV1, tenant_id: str, user_id: str, cost: int = 1) -> None:
        v = self.check(spec=spec, tenant_id=tenant_id, user_id=user_id, cost=cost)
        if not v.allowed:
            raise RuntimeError(f"RATE_LIMITED:{v.reason}:retry_after_ms={v.retry_after_ms}")
