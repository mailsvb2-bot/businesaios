from __future__ import annotations

from typing import Callable, Sequence


def best_response_price(
    *,
    candidate_prices: Sequence[float],
    demand_fn_given_competitor_price: Callable[[float], float],
    unit_cost: float,
) -> float:
    if not candidate_prices:
        raise ValueError("candidate_prices must be non-empty")
    best_price = candidate_prices[0]
    best_profit = float("-inf")
    for price in candidate_prices:
        demand = max(0.0, float(demand_fn_given_competitor_price(float(price))))
        profit = (float(price) - unit_cost) * demand
        if profit > best_profit:
            best_profit = profit
            best_price = float(price)
    return float(best_price)
