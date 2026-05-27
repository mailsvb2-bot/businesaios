from __future__ import annotations

from acquisition.feasibility_solver import AcquisitionFeasibilityRequest, FeasibilitySolver
from acquisition.funnel_model import FunnelStage
from advisory import (
    CANON_ADVISORY_ACQUISITION_RESULT_PROJECTION,
    AcquisitionExplanation,
    explain_acquisition_result,
)


def _good_request() -> AcquisitionFeasibilityRequest:
    return AcquisitionFeasibilityRequest(
        target_customers=10,
        total_budget=2200.0,
        daily_budget=200.0,
        cost_per_entry=10.0,
        gross_margin_ltv=1000.0,
        stages=(
            FunnelStage(name="traffic_to_lead", conversion_rate=0.2, avg_stage_days=3.0, touchpoints=1),
            FunnelStage(name="lead_to_meeting", conversion_rate=0.5, avg_stage_days=4.0, touchpoints=2),
            FunnelStage(name="meeting_to_sale", conversion_rate=0.5, avg_stage_days=7.0, touchpoints=3),
        ),
        target_days=20.0,
        setup_cost=100.0,
        expected_monthly_margin_per_customer=100.0,
    )


def test_result_projection_marker_is_enabled() -> None:
    assert CANON_ADVISORY_ACQUISITION_RESULT_PROJECTION is True


def test_result_projection_explains_feasible_result() -> None:
    explanation = explain_acquisition_result(FeasibilitySolver().solve(_good_request()))
    assert isinstance(explanation, AcquisitionExplanation)
    assert explanation.status == "feasible"
    assert explanation.primary_constraint in {"funnel_cycle", "balanced", "daily_budget"}


def test_result_projection_prioritizes_unit_economics_when_needed() -> None:
    result = FeasibilitySolver().solve(
        AcquisitionFeasibilityRequest(
            target_customers=10,
            total_budget=2000.0,
            daily_budget=200.0,
            cost_per_entry=10.0,
            gross_margin_ltv=300.0,
            stages=(FunnelStage(name="traffic_to_sale", conversion_rate=0.1, avg_stage_days=14.0, touchpoints=4),),
            target_days=60.0,
            expected_monthly_margin_per_customer=5.0,
            payback_horizon_months=6.0,
        )
    )
    explanation = explain_acquisition_result(result)
    assert explanation.status == "infeasible"
    assert explanation.primary_constraint == "unit_economics"
