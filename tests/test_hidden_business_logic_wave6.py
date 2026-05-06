from __future__ import annotations

from config.economics_evaluation_policy import LTVCACEvaluatorPolicy, MarginBuilderPolicy
from core.economics.builders.margin_builder import MarginBuilder
from core.economics.enums import EconomicsSignalStatus, MarginHealthStatus
from core.economics.evaluators.ltv_cac_evaluator import LTVCACEvaluator
from core.economics.policies.spend_cap_policy import SpendCapPolicy
from core.economics.types import BudgetEnvelope, CACSnapshot, CostSignal, LTVSnapshot, RevenueSignal, SpendSignal
from core.economics.enums import BudgetPressureLevel


def test_margin_builder_honors_policy_thresholds() -> None:
    builder = MarginBuilder(policy=MarginBuilderPolicy(weak_net_margin_threshold=0.10, stable_net_margin_threshold=0.30))
    snapshot = builder.build(
        revenue=RevenueSignal(period_days=30, gross_revenue=100.0, net_revenue=100.0, orders=10),
        cost=CostSignal(period_days=30, cogs=40.0, fixed_costs=10.0, variable_costs=30.0),
        spend=SpendSignal(period_days=30, marketing_spend=2.0, sales_spend=2.0, operations_spend=2.0),
    )
    assert snapshot.net_margin_ratio == 0.14
    assert snapshot.status == MarginHealthStatus.STABLE


def test_ltv_cac_evaluator_honors_policy_thresholds() -> None:
    evaluator = LTVCACEvaluator(policy=LTVCACEvaluatorPolicy(healthy_ratio_threshold=4.0, warning_ratio_threshold=2.0))
    status = evaluator.evaluate(LTVSnapshot(ltv=3.0), CACSnapshot(blended_cac=1.0))
    assert status == EconomicsSignalStatus.WARNING


def test_spend_cap_policy_defaults_to_owner_zero_floor() -> None:
    advice = SpendCapPolicy().advise(
        BudgetEnvelope(
            available_growth_budget=0.0,
            protected_cash_reserve=0.0,
            recommended_spend_cap=-15.0,
            pressure_level=BudgetPressureLevel.HIGH,
        )
    )
    assert advice.hard_cap == 0.0
    assert advice.soft_cap == 0.0
