from __future__ import annotations

from acquisition.feasibility_solver import AcquisitionFeasibilityRequest, FeasibilitySolver
from acquisition.funnel_model import FunnelStage


def test_scenario_large_target_with_very_small_budget_is_still_budget_infeasible() -> None:
    result = FeasibilitySolver().solve(
        AcquisitionFeasibilityRequest(
            target_customers=100,
            total_budget=50.0,
            daily_budget=10.0,
            cost_per_entry=10.0,
            gross_margin_ltv=1000.0,
            stages=(
                FunnelStage(name="traffic_to_lead", conversion_rate=0.2, avg_stage_days=3.0, touchpoints=1),
                FunnelStage(name="lead_to_meeting", conversion_rate=0.5, avg_stage_days=4.0, touchpoints=2),
                FunnelStage(name="meeting_to_sale", conversion_rate=0.5, avg_stage_days=7.0, touchpoints=3),
            ),
            target_days=20.0,
            expected_monthly_margin_per_customer=100.0,
        )
    )

    assert result.feasible is False
    assert result.customer_gap > 0
    assert result.budget_gap > 0.0
    assert result.timeline.feasible_in_target_window is False
    assert "budget_below_required" in result.reasons
    assert "budget_cannot_buy_enough_entries" in result.reasons
