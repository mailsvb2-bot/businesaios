from __future__ import annotations

from dataclasses import dataclass

CANON_COMPAT_SHIM = True

@dataclass(frozen=True)
class GrowthTrustPolicy:
    success_weight: float = 2.0
    failure_weight: float = 3.0
    blocked_weight: float = 1.0
    event_limit: int = 1000
    min_score: float = 0.0
    max_score: float = 100.0
    autopilot_threshold: float = 20.0
    initial_score: float = 0.0


DEFAULT_GROWTH_TRUST_POLICY = GrowthTrustPolicy()
