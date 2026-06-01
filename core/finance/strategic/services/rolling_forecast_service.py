from __future__ import annotations

from core.finance.strategic.builders.burn_rate_builder import BurnRateBuilder
from core.finance.strategic.builders.cashflow_forecast_builder import CashflowForecastBuilder
from core.finance.strategic.builders.cost_forecast_builder import CostForecastBuilder
from core.finance.strategic.builders.margin_forecast_builder import MarginForecastBuilder
from core.finance.strategic.builders.revenue_forecast_builder import RevenueForecastBuilder
from core.finance.strategic.forecasting.forecast_assumptions import ForecastAssumptions
from core.finance.strategic.forecasting.forecast_versioning import ForecastVersioning
from core.finance.strategic.types import FinancialInput, ForecastSnapshot


class RollingForecastService:
    def __init__(self, assumptions: ForecastAssumptions, versioning: ForecastVersioning) -> None:
        self._assumptions = assumptions
        self._versioning = versioning
        self._revenue = RevenueForecastBuilder()
        self._costs = CostForecastBuilder()
        self._margin = MarginForecastBuilder()
        self._cashflow = CashflowForecastBuilder()
        self._burn = BurnRateBuilder()

    def build(self, finance_input: FinancialInput) -> ForecastSnapshot:
        assumptions = self._assumptions.build(finance_input)
        revenue = self._revenue.build(finance_input)
        costs = self._costs.build(finance_input)
        margin = self._margin.build(revenue, costs)
        cashflow = self._cashflow.build(margin)
        burn = self._burn.build(cashflow)
        version = self._versioning.build_version(assumptions)
        return ForecastSnapshot(revenue=revenue, costs=costs, margin=margin, cashflow=cashflow, burn_rate=burn, assumptions_version=version)
