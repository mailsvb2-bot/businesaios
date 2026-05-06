from __future__ import annotations

"""LLM provider rate limiting.

Why this file exists:
- callers want a tiny, dependency-free limiter with an `allow(tenant_id)` API
- infra must NOT be duplicated across subsystems

Canonical infra lives in `core.ratelimit.token_bucket`.
This module is just a small adapter around that implementation.
"""

from dataclasses import dataclass

from config.llm_ratelimit_policy import DEFAULT_LLM_RATELIMIT_POLICY, LLMRateLimitPolicy

from core.ratelimit.token_bucket import (
    MemoryRateLimitStore,
    RateLimitKey,
    RateLimitPolicy,
    TokenBucketLimiter as _TokenBucketLimiter,
)
from core.tenancy.scope import TenantId


@dataclass(frozen=True)
class _Cfg:
    global_rps: float
    global_burst: int
    tenant_rps: float
    tenant_burst: int
    policy: LLMRateLimitPolicy


class TokenBucketLimiter:
    """Simple token bucket limiter for RPS control.

    Canonical behavior:
    - a global bucket protects the upstream provider
    - an optional per-tenant bucket prevents noisy neighbors
    """

    def __init__(
        self,
        *,
        global_rps: float,
        global_burst: int,
        tenant_rps: float = DEFAULT_LLM_RATELIMIT_POLICY.tenant_rps,
        tenant_burst: int = DEFAULT_LLM_RATELIMIT_POLICY.tenant_burst,
        store=None,
        policy: LLMRateLimitPolicy = DEFAULT_LLM_RATELIMIT_POLICY,
    ) -> None:
        self._cfg = _Cfg(
            global_rps=float(global_rps),
            global_burst=int(global_burst),
            tenant_rps=float(tenant_rps),
            tenant_burst=int(tenant_burst),
            policy=policy,
        )
        self._store = store or MemoryRateLimitStore()
        self._limiter = _TokenBucketLimiter(self._store)

    def _policy(self, *, rps: float, burst: int) -> RateLimitPolicy:
        cfg = self._cfg.policy
        burst_i = max(int(cfg.min_burst), int(burst))
        rps_f = max(float(cfg.min_rps), float(rps))
        # TokenBucketLimiter expects refill/sec; keep burst as capacity.
        return RateLimitPolicy(capacity=burst_i, refill_per_sec=rps_f)

    def allow(self, tenant_id: str) -> bool:
        cfg = self._cfg

        # Global bucket
        g_key = RateLimitKey(
            tenant_id=TenantId(cfg.policy.global_tenant_id),
            subject=cfg.policy.global_subject,
            bucket=cfg.policy.global_bucket,
        )
        g = self._limiter.check(
            key=g_key,
            policy=self._policy(rps=cfg.global_rps, burst=cfg.global_burst),
            cost=cfg.policy.check_cost,
        )
        if not g.allowed:
            return False

        # Optional per-tenant bucket
        if cfg.tenant_rps > cfg.policy.min_rps and cfg.tenant_burst > 0:
            t_key = RateLimitKey(
                tenant_id=TenantId(str(tenant_id)),
                subject=cfg.policy.tenant_subject,
                bucket=cfg.policy.tenant_bucket,
            )
            t = self._limiter.check(
                key=t_key,
                policy=self._policy(rps=cfg.tenant_rps, burst=cfg.tenant_burst),
                cost=cfg.policy.check_cost,
            )
            if not t.allowed:
                return False

        return True
