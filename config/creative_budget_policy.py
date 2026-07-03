from __future__ import annotations

from dataclasses import dataclass

CANON_COMPAT_SHIM = True

@dataclass(frozen=True)
class CreativeBudgetPolicy:
    confidence_readiness_weight: float = 0.60
    expected_value_weight: float = 0.40
    floor_strength_multiplier: float = 0.02
    target_base_pct: float = 0.05
    target_strength_multiplier: float = 0.25
    target_risk_drag_multiplier: float = 0.70
    ceiling_base_pct: float = 0.10
    ceiling_strength_multiplier: float = 0.40
    ceiling_risk_drag_multiplier: float = 0.50
    increase_bias_ev_threshold: float = 0.20
    increase_bias_downside_threshold: float = 0.40
    decrease_bias_ev_threshold: float = 0.0
    decrease_bias_downside_threshold: float = 0.65


DEFAULT_CREATIVE_BUDGET_POLICY = CreativeBudgetPolicy()
