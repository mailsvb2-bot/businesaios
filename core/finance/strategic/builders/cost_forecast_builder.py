from __future__ import annotations

from decimal import Decimal

from core.finance.strategic.builders._forecast_math import geometric_series
from core.finance.strategic.types import FinancialInput


class CostForecastBuilder:
    def build(self, finance_input: FinancialInput) -> list[Decimal]:
        cost_growth = max(finance_input.growth_rate * Decimal("0.7"), Decimal("-0.15"))
        return geometric_series(finance_input.costs, cost_growth, finance_input.period_months)
