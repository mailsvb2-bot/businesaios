from __future__ import annotations

from dataclasses import dataclass

CANON_COMPAT_SHIM = True

@dataclass(frozen=True)
class AdsCircuitBreakerPolicy:
    threshold: int = 5
    cooldown_s: float = 60.0
    last_failure_zero: int = 0


@dataclass(frozen=True)
class AdsRateLimiterPolicy:
    rate: float = 5.0
    burst: int = 10
    default_consume_tokens: float = 1.0


DEFAULT_ADS_CIRCUIT_BREAKER_POLICY = AdsCircuitBreakerPolicy()
DEFAULT_ADS_RATE_LIMITER_POLICY = AdsRateLimiterPolicy()
