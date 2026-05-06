from decimal import Decimal

from config.strategic_finance_simulation_policy import (
    CashflowForecastBuilderPolicy,
    CohortLTVBuilderPolicy,
    DownsideSimulatorPolicy,
    MonteCarloSimulatorPolicy,
    PaybackDistributionBuilderPolicy,
    StressCaseBuilderPolicy,
    UnsafeGrowthGuardPolicy,
)
from core.finance.strategic.builders.cashflow_forecast_builder import CashflowForecastBuilder
from core.finance.strategic.builders.cohort_ltv_builder import CohortLTVBuilder
from core.finance.strategic.builders.payback_distribution_builder import PaybackDistributionBuilder
from core.finance.strategic.builders.stress_case_builder import StressCaseBuilder
from core.finance.strategic.guards.unsafe_growth_guard import UnsafeGrowthGuard
from core.finance.strategic.simulation.downside_simulator import DownsideSimulator
from core.finance.strategic.simulation.monte_carlo_simulator import MonteCarloSimulator
from core.finance.strategic.types import FinancialInput


def test_cashflow_forecast_builder_uses_policy_default_capex_rate() -> None:
    builder = CashflowForecastBuilder(policy=CashflowForecastBuilderPolicy(default_capex_rate=Decimal('0.10')))
    assert builder.build([Decimal('100.00')]) == [Decimal('90.00')]


def test_cohort_ltv_builder_uses_policy_floors() -> None:
    finance_input = FinancialInput(
        tenant_id='t1',
        correlation_id='c1',
        period_months=1,
        revenue=Decimal('1000'),
        costs=Decimal('400'),
        cash=Decimal('500'),
        customers=10,
        churn_rate=Decimal('0'),
        gross_margin_rate=Decimal('-0.10'),
    )
    builder = CohortLTVBuilder(
        policy=CohortLTVBuilderPolicy(minimum_churn_floor=Decimal('0.05'), minimum_margin_floor=Decimal('0.25'))
    )
    assert builder.build(finance_input) == Decimal('500.00')


def test_payback_distribution_builder_uses_policy_month_floor() -> None:
    builder = PaybackDistributionBuilder(
        policy=PaybackDistributionBuilderPolicy(months_per_year=Decimal('6'), minimum_monthly_value_floor=Decimal('2'))
    )
    assert builder.build(Decimal('6'), {'search': Decimal('12')}) == {'search': Decimal('6.00')}


def test_stress_case_builder_uses_policy_values() -> None:
    scenario = StressCaseBuilder(
        policy=StressCaseBuilderPolicy(name='stress_plus', revenue_multiplier=Decimal('0.7'), probability=Decimal('0.3'))
    ).build()
    assert scenario.name == 'stress_plus'
    assert scenario.revenue_multiplier == Decimal('0.7')
    assert scenario.probability == Decimal('0.3')


def test_unsafe_growth_guard_uses_policy_defaults() -> None:
    result = UnsafeGrowthGuard(policy=UnsafeGrowthGuardPolicy(max_growth=Decimal('0.10'), minimum_margin=Decimal('0.50'))).check(
        growth_rate=Decimal('0.20'),
        gross_margin_rate=Decimal('0.30'),
    )
    assert result.ok is False


def test_downside_simulator_uses_policy_defaults() -> None:
    result = DownsideSimulator(
        policy=DownsideSimulatorPolicy(default_downside_revenue=Decimal('0.20'), default_downside_cost=Decimal('0.05'))
    ).run(Decimal('100'), Decimal('40'))
    assert result == {'revenue': Decimal('80.00'), 'costs': Decimal('42.00'), 'margin': Decimal('38.00')}


def test_monte_carlo_simulator_uses_policy_defaults_and_seed() -> None:
    simulator = MonteCarloSimulator(
        policy=MonteCarloSimulatorPolicy(default_draws=3, default_spread=Decimal('0.02'), default_seed=11)
    )
    assert simulator.run(Decimal('100.00')) == [Decimal('100.31'), Decimal('100.86'), Decimal('101.99')]
