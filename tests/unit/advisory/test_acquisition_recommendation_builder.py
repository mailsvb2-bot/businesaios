from __future__ import annotations

from acquisition.feasibility_solver import AcquisitionFeasibilityRequest, FeasibilitySolver
from acquisition.funnel_model import FunnelStage
from advisory import (
    CANON_ADVISORY_ACQUISITION_RECOMMENDATION_BUILDER,
    AcquisitionRecommendation,
    AcquisitionRecommendations,
    build_acquisition_recommendations,
)


def _baseline_stages() -> tuple[FunnelStage, ...]:
    return (
        FunnelStage(name="traffic_to_lead", conversion_rate=0.2, avg_stage_days=3.0, touchpoints=1),
        FunnelStage(name="lead_to_meeting", conversion_rate=0.5, avg_stage_days=4.0, touchpoints=2),
        FunnelStage(name="meeting_to_sale", conversion_rate=0.5, avg_stage_days=7.0, touchpoints=3),
    )


def test_recommendation_builder_marker_is_enabled() -> None:
    assert CANON_ADVISORY_ACQUISITION_RECOMMENDATION_BUILDER is True


def test_recommendation_builder_returns_keep_plan_for_feasible_result() -> None:
    result = FeasibilitySolver().solve(
        AcquisitionFeasibilityRequest(
            target_customers=10,
            total_budget=2200.0,
            daily_budget=200.0,
            cost_per_entry=10.0,
            gross_margin_ltv=1000.0,
            stages=_baseline_stages(),
            target_days=20.0,
            setup_cost=100.0,
            expected_monthly_margin_per_customer=100.0,
        )
    )

    recommendations = build_acquisition_recommendations(result)
    assert isinstance(recommendations, AcquisitionRecommendations)
    assert recommendations.items
    assert recommendations.items[0].kind == "keep_plan"


def test_recommendation_builder_suggests_budget_increase_for_budget_gap() -> None:
    result = FeasibilitySolver().solve(
        AcquisitionFeasibilityRequest(
            target_customers=50,
            total_budget=100.0,
            daily_budget=20.0,
            cost_per_entry=10.0,
            gross_margin_ltv=1000.0,
            stages=_baseline_stages(),
            target_days=20.0,
            expected_monthly_margin_per_customer=100.0,
        )
    )

    recommendations = build_acquisition_recommendations(result)
    kinds = {item.kind for item in recommendations.items}
    assert "increase_total_budget" in kinds


def test_recommendation_builder_suggests_timeline_extension_when_window_is_too_short() -> None:
    result = FeasibilitySolver().solve(
        AcquisitionFeasibilityRequest(
            target_customers=10,
            total_budget=2200.0,
            daily_budget=20.0,
            cost_per_entry=10.0,
            gross_margin_ltv=1000.0,
            stages=_baseline_stages(),
            target_days=2.0,
            setup_cost=100.0,
            expected_monthly_margin_per_customer=100.0,
        )
    )

    recommendations = build_acquisition_recommendations(result)
    kinds = {item.kind for item in recommendations.items}
    assert "extend_timeline" in kinds


def test_recommendation_builder_suggests_economics_fixes_when_payback_is_too_slow() -> None:
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

    recommendations = build_acquisition_recommendations(result)
    assert isinstance(recommendations.items[0], AcquisitionRecommendation)
    kinds = {item.kind for item in recommendations.items}
    assert "reduce_cac" in kinds or "speed_up_payback" in kinds


def test_recommendation_builder_does_not_push_budget_as_primary_fix_for_broken_conversion() -> None:
    result = FeasibilitySolver().solve(
        AcquisitionFeasibilityRequest(
            target_customers=10,
            total_budget=10000.0,
            daily_budget=1000.0,
            cost_per_entry=10.0,
            gross_margin_ltv=1000.0,
            stages=(FunnelStage(name="dead", conversion_rate=0.0, avg_stage_days=5.0, touchpoints=2),),
            target_days=30.0,
            expected_monthly_margin_per_customer=100.0,
        )
    )

    recommendations = build_acquisition_recommendations(result)
    assert recommendations.primary_constraint == "funnel_conversion"
    assert recommendations.items[0].kind == "repair_funnel_conversion"
