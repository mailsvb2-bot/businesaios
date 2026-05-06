from __future__ import annotations

from decimal import Decimal

from core.finance.strategic.decimal_utils import q2
from core.finance.strategic.scenarios.scenario_dimensions import EnterpriseScenarioInputs
from core.finance.strategic.types import FinancialInput, Scenario


class DownsideTreeEvaluator:
    def __init__(self, inputs: EnterpriseScenarioInputs | None = None) -> None:
        self._inputs = inputs or EnterpriseScenarioInputs()

    def score(self, finance_input: FinancialInput, scenario: Scenario) -> Decimal:
        view = self._inputs.from_financial_input(finance_input)
        explicit = sum((scenario.downside_tree_weights.get(name, Decimal('0.02')) for name in scenario.downside_tree), start=Decimal('0'))
        wc_penalty = q2(
            (view.receivable_days * scenario.working_capital_dynamics.get('receivable_days_stretch', Decimal('0')))
            + (view.inventory_days * scenario.working_capital_dynamics.get('inventory_days_build', Decimal('0')))
            - (view.payable_days * scenario.working_capital_dynamics.get('payable_days_support', Decimal('0')))
        )
        return q2(explicit + wc_penalty)
