from __future__ import annotations

from dataclasses import dataclass

CANON_COMPAT_SHIM = True

@dataclass(frozen=True)
class ObservabilityPerfPolicy:
    hash_modulus: int = 10_000_000
    base_ttl_ms: int = 2000
    max_ttl_ms: int = 15_000
    elevated_latency_p95_ms: float = 250.0
    severe_latency_p95_ms: float = 500.0
    elevated_ttl_multiplier: int = 3
    severe_ttl_multiplier: int = 5
    missing_latency_p95_ms: float = 0.0


DEFAULT_OBSERVABILITY_PERF_POLICY = ObservabilityPerfPolicy()


__all__ = ["ObservabilityPerfPolicy", "DEFAULT_OBSERVABILITY_PERF_POLICY"]
