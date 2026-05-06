from __future__ import annotations

def point_price_elasticity(
    *,
    demand_derivative_wrt_price: float,
    price: float,
    quantity: float,
) -> float:
    if quantity == 0:
        raise ValueError("quantity must be non-zero")
    return float(demand_derivative_wrt_price) * float(price) / float(quantity)
