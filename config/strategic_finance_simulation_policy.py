from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class CashflowForecastBuilderPolicy:
    default_capex_rate: Decimal = Decimal('0.05')
    minimum_capex_rate: Decimal = Decimal('0')
    maximum_capex_rate: Decimal = Decimal('1')


@dataclass(frozen=True)
class CohortLTVBuilderPolicy:
    zero_value: Decimal = Decimal('0')
    minimum_customers_floor: int = 1
    minimum_churn_floor: Decimal = Decimal('0.01')
    minimum_margin_floor: Decimal = Decimal('0')


@dataclass(frozen=True)
class PaybackDistributionBuilderPolicy:
    months_per_year: Decimal = Decimal('12')
    minimum_monthly_value_floor: Decimal = Decimal('0.01')


@dataclass(frozen=True)
class StressCaseBuilderPolicy:
    name: str = 'stress'
    revenue_multiplier: Decimal = Decimal('0.8')
    cost_multiplier: Decimal = Decimal('1.1')
    probability: Decimal = Decimal('0.2')
    notes: tuple[str, ...] = ('lower demand', 'higher costs')


@dataclass(frozen=True)
class UnsafeGrowthGuardPolicy:
    max_growth: Decimal = Decimal('0.25')
    minimum_margin: Decimal = Decimal('0.40')


@dataclass(frozen=True)
class DownsideSimulatorPolicy:
    baseline_multiplier: Decimal = Decimal('1')
    default_downside_revenue: Decimal = Decimal('0.15')
    default_downside_cost: Decimal = Decimal('0.08')


@dataclass(frozen=True)
class MonteCarloSimulatorPolicy:
    default_draws: int = 100
    default_spread: Decimal = Decimal('0.1')
    default_seed: int = 7
    basis_points_multiplier: Decimal = Decimal('10000')
    baseline_multiplier: Decimal = Decimal('1')


DEFAULT_CASHFLOW_FORECAST_BUILDER_POLICY = CashflowForecastBuilderPolicy()
DEFAULT_COHORT_LTV_BUILDER_POLICY = CohortLTVBuilderPolicy()
DEFAULT_PAYBACK_DISTRIBUTION_BUILDER_POLICY = PaybackDistributionBuilderPolicy()
DEFAULT_STRESS_CASE_BUILDER_POLICY = StressCaseBuilderPolicy()
DEFAULT_UNSAFE_GROWTH_GUARD_POLICY = UnsafeGrowthGuardPolicy()
DEFAULT_DOWNSIDE_SIMULATOR_POLICY = DownsideSimulatorPolicy()
DEFAULT_MONTE_CARLO_SIMULATOR_POLICY = MonteCarloSimulatorPolicy()
