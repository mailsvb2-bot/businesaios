from __future__ import annotations

from dataclasses import dataclass

CANON_ADVISORY_REVENUE_OS_PRICING_POLICY = True


@dataclass(frozen=True, slots=True)
class PricingPolicy:
    max_price_increase_pct: float = 0.10
    max_price_decrease_pct: float = 0.15
    require_approval_above_pct: float = 0.05
    minimum_margin: float = 0.20
    allow_price_drop_when_churn_critical: bool = True

    def bounded_multiplier(self, *, desired_change_pct: float) -> float:
        change = float(desired_change_pct)
        upper = max(0.0, float(self.max_price_increase_pct))
        lower = max(0.0, float(self.max_price_decrease_pct))
        bounded = max(-lower, min(upper, change))
        return round(1.0 + bounded, 6)


__all__ = ['CANON_ADVISORY_REVENUE_OS_PRICING_POLICY', 'PricingPolicy']
