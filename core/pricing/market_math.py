from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from collections.abc import Sequence

from core.math.advanced_models import best_response_price, optimal_price_from_grid, point_price_elasticity


@dataclass(frozen=True)
class MarketPriceSummary:
    chosen_price: int
    expected_profit: float
    elasticity: float
    best_response_price_rub: int

def summarize_market_price(
    *,
    candidate_prices: Sequence[int],
    demand_fn: Callable[[float], float],
    unit_cost: float,
    demand_derivative_wrt_price: float,
    baseline_quantity: float,
    competitor_demand_fn: Callable[[float], float],
) -> MarketPriceSummary:
    decision = optimal_price_from_grid(
        candidate_prices=[float(x) for x in candidate_prices],
        demand_fn=demand_fn,
        unit_cost=float(unit_cost),
    )
    elasticity = point_price_elasticity(
        demand_derivative_wrt_price=float(demand_derivative_wrt_price),
        price=float(decision.price),
        quantity=float(max(baseline_quantity, 1.0)),
    )
    best_response = best_response_price(
        candidate_prices=[float(x) for x in candidate_prices],
        demand_fn_given_competitor_price=competitor_demand_fn,
        unit_cost=float(unit_cost),
    )
    return MarketPriceSummary(
        chosen_price=int(decision.price),
        expected_profit=float(decision.expected_profit),
        elasticity=float(elasticity),
        best_response_price_rub=int(best_response),
    )
