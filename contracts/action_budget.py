from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ActionBudget:
    currency: str = ''
    amount: float = 0.0
    daily_cap: float = 0.0


# Closed read-only routes exempted from action-budget consumption.
ADMIN_ANALYTICS_ROUTES = frozenset({
    "admin:segments", "admin:ab", "admin:giftshare", "admin:funnel2",
})
