from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass


@dataclass(frozen=True)
class DOWSeasonalityPolicy:
    neutral_multiplier: float = 1.0
    zero_accumulator: float = 0.0
    count_increment: float = 1.0


@dataclass(frozen=True)
class PricingWorldModelPolicy:
    zero_marginal_cost: float = 0.0
    default_demand_scale: float = 1.0
    default_demand_exponent: float = -1.0
    default_conversion_bias: float = -2.0
    default_conversion_slope: float = -0.01


DEFAULT_DOW_SEASONALITY_POLICY = DOWSeasonalityPolicy()
DEFAULT_PRICING_WORLD_MODEL_POLICY = PricingWorldModelPolicy()
