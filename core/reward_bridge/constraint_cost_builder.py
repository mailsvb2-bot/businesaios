from __future__ import annotations


def build_constraint_cost(
    *,
    architecture_global_stability: float,
    market_competitive_shift: float,
) -> float:
    instability = max(0.0, min(1.0, 1.0 - float(architecture_global_stability)))
    shift = max(0.0, min(1.0, float(market_competitive_shift)))
    return max(0.0, min(1.0, (0.70 * instability) + (0.30 * shift)))
