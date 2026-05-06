from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OutcomeTariff:
    qualified_lead_price: float = 0.0
    booking_price: float = 0.0
    conversion_fee_rate: float = 0.0

    def price_for(self, outcome_kind: str, revenue_amount: float = 0.0) -> float:
        if outcome_kind == 'qualified_lead':
            return float(self.qualified_lead_price)
        if outcome_kind == 'booking':
            return float(self.booking_price)
        if outcome_kind == 'conversion':
            return round(float(revenue_amount) * float(self.conversion_fee_rate), 2)
        return 0.0
