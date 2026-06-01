from __future__ import annotations

from dataclasses import dataclass

from .types import MarketContext


@dataclass(frozen=True)
class WorldModelInput:
    """Input for building a pricing-oriented world state."""

    context: MarketContext
    current_price: float
    # Optional: if you already have CAC or cost info.
    marginal_cost: float | None = None


@dataclass(frozen=True)
class PricingWorldState:
    """Derived features for pricing decisions (not the decision itself)."""

    demand_units_at_price: float
    conversion_prob_at_price: float
    point_elasticity: float
    seasonality_multiplier: float
    expected_revenue: float
    expected_profit: float

    # Useful for explainability / trace.
    demand_model: str
    conversion_model: str
    seasonality_model: str
