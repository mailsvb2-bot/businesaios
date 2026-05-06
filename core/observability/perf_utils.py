"""Perf helpers: deterministic hash and SLA-driven cache tuner.

No dependency on Span/emit_span; safe to import from anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from config.observability_perf_policy import DEFAULT_OBSERVABILITY_PERF_POLICY, ObservabilityPerfPolicy


def stable_hash_01(seed: str, *, policy: ObservabilityPerfPolicy = DEFAULT_OBSERVABILITY_PERF_POLICY) -> float:
    """Deterministic pseudo-random in [0,1)."""
    import hashlib
    s = str(seed or "").encode("utf-8")
    h = hashlib.sha256(s).digest()
    n = int.from_bytes(h[:8], "big", signed=False)
    return (n % policy.hash_modulus) / float(policy.hash_modulus)


@dataclass(frozen=True)
class AutoAccelerator:
    """SLA-driven cache window tuner (best-effort)."""
    base_ttl_ms: int = DEFAULT_OBSERVABILITY_PERF_POLICY.base_ttl_ms
    max_ttl_ms: int = DEFAULT_OBSERVABILITY_PERF_POLICY.max_ttl_ms
    policy: ObservabilityPerfPolicy = DEFAULT_OBSERVABILITY_PERF_POLICY

    def recommend_ttl_ms(self, *, latency_summary: Mapping[str, Any] | None) -> int:
        ttl = int(self.base_ttl_ms)
        if not latency_summary:
            return ttl
        try:
            router = latency_summary.get("router") or {}
            p95 = float(router.get("p95_ms") or self.policy.missing_latency_p95_ms)
        except Exception:
            p95 = self.policy.missing_latency_p95_ms
        if p95 >= self.policy.elevated_latency_p95_ms:
            ttl = min(self.max_ttl_ms, max(ttl, int(ttl * self.policy.elevated_ttl_multiplier)))
        if p95 >= self.policy.severe_latency_p95_ms:
            ttl = min(self.max_ttl_ms, max(ttl, int(ttl * self.policy.severe_ttl_multiplier)))
        return int(ttl)


__all__ = ["stable_hash_01", "AutoAccelerator"]
