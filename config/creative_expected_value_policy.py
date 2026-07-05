from __future__ import annotations

from dataclasses import dataclass

CANON_COMPAT_SHIM = True

@dataclass(frozen=True)
class CreativeExpectedValuePolicy:
    roi_weight: float = 0.35
    contribution_margin_weight: float = 0.25
    incrementality_weight: float = 0.20
    rollout_readiness_weight: float = 0.10
    future_value_weight: float = 0.10
    min_score: float = -1.0
    max_score: float = 1.0


DEFAULT_CREATIVE_EXPECTED_VALUE_POLICY = CreativeExpectedValuePolicy()
