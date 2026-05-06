from __future__ import annotations

from acquisition.feasibility_solver import AcquisitionFeasibilityRequest, FeasibilitySolver
from acquisition.funnel_model import FunnelStage


def _stages() -> tuple[FunnelStage, ...]:
    return (
        FunnelStage(name="traffic_to_lead", conversion_rate=0.4, avg_stage_days=3.0, touchpoints=1),
        FunnelStage(name="lead_to_meeting", conversion_rate=0.5, avg_stage_days=4.0, touchpoints=2),
        FunnelStage(name="meeting_to_sale", conversion_rate=0.5, avg_stage_days=7.0, touchpoints=3),
    )


def test_feasibility_solver_returns_feasible_result_for_good_plan() -> None:
    result = FeasibilitySolver().solve(AcquisitionFeasibilityRequest(target_customers=10, total_budget=1200.0, daily_budget=100.0, cost_per_entry=10.0, gross_margin_ltv=1000.0, stages=_stages(), target_days=20.0, setup_cost=100.0, max_cac_to_ltv_ratio=0.33, payback_horizon_months=12.0, expected_monthly_margin_per_customer=100.0))
    assert result.feasible is True
    assert result.customer_gap == 0
    assert result.budget_gap == 0.0
    assert result.required_budget == 1100.0
    assert result.recommended_daily_budget == 55.0
    assert result.estimated_days == 14.0
    assert result.feasibility_score == 1.0
    assert "plan is feasible" in result.summary
    assert result.timeline.affordable_customers >= 10
    assert result.cac.sustainable is True


def test_feasibility_solver_returns_infeasible_result_when_budget_and_time_fail() -> None:
    result = FeasibilitySolver().solve(AcquisitionFeasibilityRequest(target_customers=10, total_budget=200.0, daily_budget=10.0, cost_per_entry=10.0, gross_margin_ltv=100.0, stages=_stages(), target_days=5.0, setup_cost=50.0, max_cac_to_ltv_ratio=0.33, payback_horizon_months=6.0, expected_monthly_margin_per_customer=5.0))
    assert result.feasible is False
    assert result.customer_gap > 0
    assert result.budget_gap > 0.0
    assert result.feasibility_score < 1.0
    assert "plan is not feasible" in result.summary
    assert "budget_below_required" in result.reasons
    assert "budget_cannot_buy_enough_entries" in result.reasons or "timeline_exceeds_target_window" in result.reasons
    assert result.cac.sustainable is False


def test_feasibility_solver_flags_unreachable_target_with_zero_conversion() -> None:
    result = FeasibilitySolver().solve(AcquisitionFeasibilityRequest(target_customers=10, total_budget=1000.0, daily_budget=100.0, cost_per_entry=5.0, gross_margin_ltv=500.0, stages=(FunnelStage(name="dead_stage", conversion_rate=0.0, avg_stage_days=3.0),), target_days=30.0))
    assert result.feasible is False
    assert result.required_budget == 0.0
    assert result.customer_gap == 10
    assert "target_unreachable_with_current_funnel" in result.reasons
    assert "zero_funnel_conversion" in result.reasons


def test_feasibility_solver_handles_zero_cost_per_entry_conservatively() -> None:
    result = FeasibilitySolver().solve(AcquisitionFeasibilityRequest(target_customers=10, total_budget=1000.0, daily_budget=100.0, cost_per_entry=0.0, gross_margin_ltv=1000.0, stages=_stages(), target_days=30.0, expected_monthly_margin_per_customer=100.0))
    assert result.feasible is False
    assert result.customer_gap == 10
    assert "zero_cost_per_entry_assumption" in result.reasons


def test_feasibility_solver_preserves_single_flow_contract() -> None:
    result = FeasibilitySolver().solve(AcquisitionFeasibilityRequest(target_customers=8, total_budget=800.0, daily_budget=80.0, cost_per_entry=10.0, gross_margin_ltv=600.0, stages=_stages(), target_days=14.0, setup_cost=0.0, expected_monthly_margin_per_customer=60.0))
    assert result.budget.required_budget == result.required_budget
    assert result.budget.recommended_daily_budget == result.recommended_daily_budget
    assert result.timeline.estimated_days == result.estimated_days
    assert result.funnel.overall_conversion_rate > 0.0
