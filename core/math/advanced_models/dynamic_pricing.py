from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

@dataclass(frozen=True)
class PriceDecision:
    price: float
    expected_profit: float
    expected_volume: float

def optimal_price_from_grid(
    *,
    candidate_prices: Sequence[float],
    demand_fn: Callable[[float], float],
    unit_cost: float,
) -> PriceDecision:
    if not candidate_prices:
        raise ValueError("candidate_prices must be non-empty")
    best_price = None
    best_profit = float("-inf")
    best_volume = 0.0
    for price in candidate_prices:
        volume = max(0.0, float(demand_fn(float(price))))
        profit = (float(price) - unit_cost) * volume
        if profit > best_profit:
            best_profit = profit
            best_price = float(price)
            best_volume = volume
    assert best_price is not None
    return PriceDecision(price=best_price, expected_profit=best_profit, expected_volume=best_volume)
