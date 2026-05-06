from __future__ import annotations

from decimal import Decimal

from core.finance.strategic.builders._forecast_math import geometric_series
from core.finance.strategic.types import FinancialInput


class RevenueForecastBuilder:
    def build(self, finance_input: FinancialInput) -> list[Decimal]:
        return geometric_series(finance_input.revenue, finance_input.growth_rate, finance_input.period_months)
