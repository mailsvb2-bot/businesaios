from __future__ import annotations


def normalize_attribution_credit(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def attributed_revenue(
    *,
    revenue: float,
    attribution_credit: float,
) -> float:
    return max(0.0, float(revenue)) * normalize_attribution_credit(attribution_credit)
