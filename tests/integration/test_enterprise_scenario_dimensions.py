from __future__ import annotations

from decimal import Decimal

from core.finance.strategic.scenarios.downside_tree import DownsideTreeEvaluator
from core.finance.strategic.scenarios.scenario_catalog import ScenarioCatalog
from core.finance.strategic.scenarios.scenario_dimensions import EnterpriseScenarioInputs
from core.finance.strategic.types import FinancialInput


def test_scenarios_cover_enterprise_dimensions() -> None:
    scenarios = ScenarioCatalog().build()
    assert any(item.product_bias for item in scenarios)
    assert any(item.entity_bias for item in scenarios)
    assert any(item.working_capital_dynamics for item in scenarios)
    assert any(item.downside_tree_weights for item in scenarios)


def test_enterprise_inputs_and_downside_tree_affect_score() -> None:
    finance_input = FinancialInput(
        tenant_id='t1',
        correlation_id='c1',
        period_months=6,
        revenue=Decimal('1000'),
        costs=Decimal('600'),
        cash=Decimal('300'),
        metadata={
            'channel_mix': {'marketing': '0.6', 'sales': '0.4'},
            'segment_mix': {'existing': '0.7', 'new': '0.3'},
            'product_mix': {'core': '0.8', 'new_products': '0.2'},
            'entity_mix': {'group': '0.9', 'intl': '0.1'},
            'receivable_days': '45',
            'payable_days': '20',
            'inventory_days': '15',
        },
    )
    scenario = next(item for item in ScenarioCatalog().build() if item.name == 'liquidity_stress')
    inputs = EnterpriseScenarioInputs()
    view = inputs.from_financial_input(finance_input)
    assert view.receivable_days == Decimal('45')
    assert 'core' in view.products
    penalty = DownsideTreeEvaluator(inputs).score(finance_input, scenario)
    assert penalty > Decimal('0')
