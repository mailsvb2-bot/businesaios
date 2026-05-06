from __future__ import annotations

from decimal import Decimal

from core.finance.strategic.scenarios.scenario_dimensions import EnterpriseScenarioInputs
from core.finance.strategic.types import FinancialInput, Scenario


class ScenarioFeasibilityChecker:
    def __init__(self, inputs: EnterpriseScenarioInputs | None = None) -> None:
        self._inputs = inputs or EnterpriseScenarioInputs()

    def is_feasible(self, finance_input: FinancialInput, scenario: Scenario) -> bool:
        stressed_cost = finance_input.costs * scenario.cost_multiplier
        stressed_revenue = finance_input.revenue * scenario.revenue_multiplier
        stressed_cash = finance_input.cash + stressed_revenue - stressed_cost - finance_input.debt
        view = self._inputs.from_financial_input(finance_input)
        wc_drag = finance_input.revenue * scenario.working_capital_pressure
        wc_drag += view.receivable_days * scenario.working_capital_dynamics.get('receivable_days_stretch', Decimal('0'))
        wc_drag += view.inventory_days * scenario.working_capital_dynamics.get('inventory_days_build', Decimal('0'))
        wc_drag -= view.payable_days * scenario.working_capital_dynamics.get('payable_days_support', Decimal('0'))
        working_capital_headroom = stressed_cash - wc_drag
        return working_capital_headroom > Decimal('0')
