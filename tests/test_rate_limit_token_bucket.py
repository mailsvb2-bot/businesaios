from core.ratelimit.token_bucket import (
    MemoryRateLimitStore,
    TokenBucketLimiter,
    RateLimitKey,
    RateLimitPolicy,
)
from core.tenancy.scope import TenantId


def test_token_bucket_basic_allows_then_blocks():
    store = MemoryRateLimitStore()
    limiter = TokenBucketLimiter(store)
    key = RateLimitKey(tenant_id=TenantId("t1"), subject="u1", bucket="ep")

    policy = RateLimitPolicy(capacity=2, refill_per_sec=0.0)

    d1 = limiter.check(key=key, policy=policy)
    d2 = limiter.check(key=key, policy=policy)
    d3 = limiter.check(key=key, policy=policy)

    assert d1.allowed is True
    assert d2.allowed is True
    assert d3.allowed is False
    assert d3.retry_after_ms > 0
