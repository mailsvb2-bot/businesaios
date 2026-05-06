from acquisition.feasibility_solver import AcquisitionFeasibilityRequest, FeasibilitySolver
from acquisition.funnel_model import FunnelStage


def test_feasibility_solver_uses_policy_based_partial_credit_for_unsustainable_plan():
    result = FeasibilitySolver().solve(
        AcquisitionFeasibilityRequest(
            target_customers=10,
            total_budget=1000.0,
            daily_budget=100.0,
            cost_per_entry=5.0,
            gross_margin_ltv=10.0,
            stages=(FunnelStage(name="visit", conversion_rate=0.5, avg_stage_days=1.0), FunnelStage(name="buy", conversion_rate=0.5, avg_stage_days=1.0)),
            target_days=30.0,
            expected_monthly_margin_per_customer=1.0,
        )
    )
    assert result.feasibility_score <= 0.5
