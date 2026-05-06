from __future__ import annotations

from decimal import Decimal

from config.strategic_finance_simulation_policy import (
    DEFAULT_COHORT_LTV_BUILDER_POLICY,
    CohortLTVBuilderPolicy,
)
from core.finance.strategic.decimal_utils import q2
from core.finance.strategic.types import FinancialInput


class CohortLTVBuilder:
    def __init__(self, policy: CohortLTVBuilderPolicy = DEFAULT_COHORT_LTV_BUILDER_POLICY) -> None:
        self._policy = policy

    def build(self, finance_input: FinancialInput) -> Decimal:
        if finance_input.customers <= 0:
            return self._policy.zero_value
        gross_profit = finance_input.revenue * max(finance_input.gross_margin_rate, self._policy.minimum_margin_floor)
        monthly_value = gross_profit / Decimal(max(finance_input.customers, self._policy.minimum_customers_floor))
        churn = max(finance_input.churn_rate, self._policy.minimum_churn_floor)
        return q2(monthly_value / churn)
