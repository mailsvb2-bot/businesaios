from __future__ import annotations

from acquisition.feasibility_solver import AcquisitionFeasibilityRequest, FeasibilitySolver
from acquisition.funnel_model import FunnelStage
from presentation import (
    CANON_PRESENTATION_ACQUISITION_VIEW_MODEL,
    AcquisitionRecommendationView,
    AcquisitionViewModel,
    build_acquisition_view_model,
)


def _baseline_request() -> AcquisitionFeasibilityRequest:
    return AcquisitionFeasibilityRequest(
        target_customers=10,
        total_budget=2200.0,
        daily_budget=200.0,
        cost_per_entry=10.0,
        gross_margin_ltv=1000.0,
        stages=(
            FunnelStage(name='traffic_to_lead', conversion_rate=0.2, avg_stage_days=3.0, touchpoints=1),
            FunnelStage(name='lead_to_meeting', conversion_rate=0.5, avg_stage_days=4.0, touchpoints=2),
            FunnelStage(name='meeting_to_sale', conversion_rate=0.5, avg_stage_days=7.0, touchpoints=3),
        ),
        target_days=20.0,
        setup_cost=100.0,
        expected_monthly_margin_per_customer=100.0,
    )


def test_view_model_marker_is_enabled() -> None:
    assert CANON_PRESENTATION_ACQUISITION_VIEW_MODEL is True


def test_view_model_builds_feasible_ui_shape() -> None:
    result = FeasibilitySolver().solve(_baseline_request())
    vm = build_acquisition_view_model(result)
    assert isinstance(vm, AcquisitionViewModel)
    assert vm.feasible is True
    assert vm.status == 'feasible'
    assert 'План достижим' in vm.headline
    assert vm.achievable_customers >= 10
    assert vm.required_budget == 2100.0
    assert vm.recommended_daily_budget == 105.0
    assert vm.recommendations
    assert isinstance(vm.recommendations[0], AcquisitionRecommendationView)


def test_view_model_builds_infeasible_ui_shape() -> None:
    result = FeasibilitySolver().solve(
        AcquisitionFeasibilityRequest(
            target_customers=120,
            total_budget=50.0,
            daily_budget=50.0,
            cost_per_entry=1.0,
            gross_margin_ltv=200.0,
            stages=_baseline_request().stages,
            target_days=3.0,
            expected_monthly_margin_per_customer=20.0,
        )
    )
    vm = build_acquisition_view_model(result)
    assert vm.feasible is False
    assert vm.status == 'infeasible'
    assert vm.customer_gap > 0
    assert vm.budget_gap > 0.0
    assert vm.recommendations
