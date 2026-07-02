from __future__ import annotations

from dataclasses import dataclass

CANON_COMPAT_SHIM = True


@dataclass(frozen=True)
class StrategicHorizonPolicy:
    min_runway_defense: int = 21
    min_runway_stabilize: int = 45
    min_margin_safe: float = 0.15
    max_risk_budget: float = 1.0
    min_risk_budget: float = 0.05
    mode_cooldown_seconds: int = 60 * 60 * 6


DEFAULT_STRATEGIC_HORIZON_POLICY = StrategicHorizonPolicy()
