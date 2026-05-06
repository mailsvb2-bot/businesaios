from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass


@dataclass(frozen=True)
class CircuitBreakerPolicy:
    closed_until_s: float = 0.0
    fail_threshold: int = 5
    open_for_s: float = 120.0


DEFAULT_CIRCUIT_BREAKER_POLICY = CircuitBreakerPolicy()
