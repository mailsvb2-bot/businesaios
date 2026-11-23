"""LLM-specific adapter for the canonical core.ratelimit.token_bucket."""

from __future__ import annotations

from dataclasses import dataclass

from config.llm_ratelimit_policy import DEFAULT_LLM_RATELIMIT_POLICY, LLMRateLimitPolicy
from core.ratelimit.token_bucket import (
    MemoryRateLimitStore,
    RateLimitKey,
    RateLimitPolicy,
)
from core.ratelimit.token_bucket import (
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
    """Two scoped buckets share one canonical limiter and backing store."""

    def __init__(
        self, *, global_rps: float, global_burst: int,
        tenant_rps: float = DEFAULT_LLM_RATELIMIT_POLICY.tenant_rps,
        tenant_burst: int = DEFAULT_LLM_RATELIMIT_POLICY.tenant_burst,
        store=None, policy: LLMRateLimitPolicy = DEFAULT_LLM_RATELIMIT_POLICY,
    ) -> None:
        self._cfg = _Cfg(float(global_rps), int(global_burst), float(tenant_rps), int(tenant_burst), policy)
        self._store = store or MemoryRateLimitStore()
        self._limiter = _TokenBucketLimiter(self._store)

    def _policy(self, *, rps: float, burst: int) -> RateLimitPolicy:
        return RateLimitPolicy(capacity=max(int(self._cfg.policy.min_burst), int(burst)), refill_per_sec=max(float(self._cfg.policy.min_rps), float(rps)))

    def allow(self, tenant_id: str) -> bool:
        cfg = self._cfg
        def check(tenant: str, subject: str, bucket: str, rps: float, burst: int) -> bool:
            return self._limiter.check(
                key=RateLimitKey(tenant_id=TenantId(tenant), subject=subject, bucket=bucket),
                policy=self._policy(rps=rps, burst=burst), cost=cfg.policy.check_cost,
            ).allowed

        if not check(cfg.policy.global_tenant_id, cfg.policy.global_subject,
                     cfg.policy.global_bucket, cfg.global_rps, cfg.global_burst):
            return False
        return not (cfg.tenant_rps > cfg.policy.min_rps and cfg.tenant_burst > 0) or check(
            str(tenant_id), cfg.policy.tenant_subject, cfg.policy.tenant_bucket,
            cfg.tenant_rps, cfg.tenant_burst,
        )
