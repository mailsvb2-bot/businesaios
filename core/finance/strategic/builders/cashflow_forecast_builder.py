from __future__ import annotations

from decimal import Decimal

from config.strategic_finance_simulation_policy import (
    DEFAULT_CASHFLOW_FORECAST_BUILDER_POLICY,
    CashflowForecastBuilderPolicy,
)
from core.finance.strategic.decimal_utils import q2


class CashflowForecastBuilder:
    def __init__(self, policy: CashflowForecastBuilderPolicy = DEFAULT_CASHFLOW_FORECAST_BUILDER_POLICY) -> None:
        self._policy = policy

    def build(self, margin: list[Decimal], capex_rate: Decimal | None = None) -> list[Decimal]:
        rate = self._policy.default_capex_rate if capex_rate is None else capex_rate
        if not self._policy.minimum_capex_rate <= rate <= self._policy.maximum_capex_rate:
            raise ValueError('capex_rate must be between 0 and 1')
        return [q2(item * (Decimal('1') - rate)) for item in margin]
