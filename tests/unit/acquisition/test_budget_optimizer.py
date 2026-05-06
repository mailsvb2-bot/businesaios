from __future__ import annotations

from acquisition.budget_optimizer import BudgetOptimizer, BudgetOptimizerInputs
from acquisition.funnel_model import FunnelModel, FunnelStage


def _funnel_snapshot():
    return FunnelModel().summarize((FunnelStage(name="lead", conversion_rate=0.5, avg_stage_days=5.0), FunnelStage(name="sale", conversion_rate=0.2, avg_stage_days=5.0)))


def test_budget_optimizer_computes_required_budget_and_gap() -> None:
    result = BudgetOptimizer().recommend(BudgetOptimizerInputs(target_customers=10, cost_per_entry=2.0, funnel=_funnel_snapshot(), setup_cost=50.0, target_days=20.0, available_budget=200.0))
    assert result.required_entries == 100
    assert result.required_budget == 250.0
    assert result.recommended_daily_budget == 12.5
    assert result.budget_gap == 50.0
    assert result.is_budget_sufficient is False
    assert "budget_below_required" in result.reasons


def test_budget_optimizer_marks_budget_as_sufficient_when_enough() -> None:
    result = BudgetOptimizer().recommend(BudgetOptimizerInputs(target_customers=10, cost_per_entry=2.0, funnel=_funnel_snapshot(), setup_cost=0.0, target_days=10.0, available_budget=250.0))
    assert result.required_entries == 100
    assert result.required_budget == 200.0
    assert result.budget_gap == 0.0
    assert result.is_budget_sufficient is True


def test_budget_optimizer_uses_funnel_cycle_when_target_days_not_provided() -> None:
    result = BudgetOptimizer().recommend(BudgetOptimizerInputs(target_customers=10, cost_per_entry=1.0, funnel=_funnel_snapshot(), setup_cost=0.0, target_days=0.0, available_budget=100.0))
    assert result.required_budget == 100.0
    assert result.recommended_daily_budget == 10.0


def test_budget_optimizer_flags_zero_conversion_funnel() -> None:
    funnel = FunnelModel().summarize((FunnelStage(name="dead", conversion_rate=0.0),))
    result = BudgetOptimizer().recommend(BudgetOptimizerInputs(target_customers=10, cost_per_entry=3.0, funnel=funnel, available_budget=0.0))
    assert result.required_entries == 0
    assert result.required_budget == 0.0
    assert "zero_funnel_conversion" in result.reasons
