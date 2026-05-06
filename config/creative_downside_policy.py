from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass


@dataclass(frozen=True)
class CreativeDownsidePolicy:
    pnl_risk_weight: float = 0.45
    causal_risk_weight: float = 0.35
    confidence_risk_weight: float = 0.20
    min_score: float = 0.0
    max_score: float = 1.0
    confidence_floor: float = 1.0


DEFAULT_CREATIVE_DOWNSIDE_POLICY = CreativeDownsidePolicy()
