from __future__ import annotations

from core.economics.builders.policy_advice_builder import EconomicsPolicyAdviceBuilder
from core.economics.enums import GuardSeverity
from core.economics.guards.advisory_boundary_guard import AdvisoryBoundaryGuard
from core.economics.guards.currency_consistency_guard import CurrencyConsistencyGuard
from core.economics.guards.signal_period_guard import SignalPeriodGuard
from core.economics.types import (
    CashflowSignal,
    CostSignal,
    CustomerValueSignal,
    EconomicsReadModel,
    RevenueSignal,
    SpendSignal,
)


def _read_model() -> EconomicsReadModel:
    return EconomicsReadModel(
        revenue=RevenueSignal(period_days=30, gross_revenue=1200.0, net_revenue=1000.0, orders=10, currency="USD"),
        cost=CostSignal(period_days=30, cogs=200.0, fixed_costs=100.0, variable_costs=50.0, currency="USD"),
        spend=SpendSignal(period_days=30, marketing_spend=100.0, sales_spend=50.0, operations_spend=25.0, currency="USD"),
        customer_value=CustomerValueSignal(active_customers=20, new_customers=5, returning_customers=15, average_order_value=50.0, purchase_frequency_30d=1.2, gross_retention_30d=0.8),
        cashflow=CashflowSignal(cash_in=1200.0, cash_out=700.0, runway_days=120, unrestricted_cash=5000.0, currency="USD"),
    )


def test_economics_policy_advice_is_advisory_only():
    advice = EconomicsPolicyAdviceBuilder().build(
        budget=type('B', (), {'recommended_spend_cap': 100.0, 'pressure_level': type('P', (), {'value': 'low'})()})
    )
    trigger = AdvisoryBoundaryGuard().check(advice)
    assert trigger is None


def test_signal_period_guard_blocks_mismatch():
    read_model = _read_model()
    read_model = EconomicsReadModel(
        revenue=read_model.revenue,
        cost=CostSignal(period_days=7, cogs=200.0, fixed_costs=100.0, variable_costs=50.0, currency="USD"),
        spend=read_model.spend,
        customer_value=read_model.customer_value,
        cashflow=read_model.cashflow,
    )
    trigger = SignalPeriodGuard().check(read_model)
    assert trigger is not None
    assert trigger.severity == GuardSeverity.BLOCK


def test_currency_guard_blocks_mismatch():
    read_model = _read_model()
    read_model = EconomicsReadModel(
        revenue=read_model.revenue,
        cost=read_model.cost,
        spend=SpendSignal(period_days=30, marketing_spend=1.0, sales_spend=1.0, operations_spend=1.0, currency="EUR"),
        customer_value=read_model.customer_value,
        cashflow=read_model.cashflow,
    )
    trigger = CurrencyConsistencyGuard().check(read_model)
    assert trigger is not None
    assert trigger.severity == GuardSeverity.BLOCK
