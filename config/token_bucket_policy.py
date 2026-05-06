from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass


@dataclass(frozen=True)
class TokenBucketPolicyDefaults:
    zero_tokens: float = 0.0
    default_take_tokens: float = 1.0
    milliseconds_per_second: int = 1000
    anonymous_subject: str = "anonymous"
    default_bucket: str = "default"
    transport_tenant_id: str = "transport"
    transport_subject: str = "global"
    min_capacity: int = 1
    min_cost: int = 1
    min_retry_seconds: float = 0.01
    fallback_retry_seconds: float = 60.0
    async_min_sleep_s: float = 0.02


DEFAULT_TOKEN_BUCKET_POLICY_DEFAULTS = TokenBucketPolicyDefaults()
