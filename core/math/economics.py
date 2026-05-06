from __future__ import annotations

from config.economics_domain_policy import DEFAULT_ECONOMICS_MATH_POLICY


def ltv(arpu: float, lifetime: float) -> float:
    """LTV = ARPU * Lifetime"""
    return float(arpu) * float(lifetime)


def cac(marketing_spend: float, users_acquired: float) -> float:
    """CAC = Marketing / Users"""
    users = float(users_acquired)
    zero_value = DEFAULT_ECONOMICS_MATH_POLICY.zero_value
    if users <= zero_value:
        return zero_value
    return float(marketing_spend) / users


def unit_profit(*, arpu: float, lifetime: float, marketing_spend: float, users_acquired: float) -> float:
    """Profit = LTV - CAC"""
    return ltv(arpu, lifetime) - cac(marketing_spend, users_acquired)
