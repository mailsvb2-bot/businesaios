from __future__ import annotations

from acquisition.feasibility_solver import AcquisitionFeasibilityRequest, FeasibilitySolver
from acquisition.funnel_model import FunnelStage
from advisory import (
    CANON_ADVISORY_ACQUISITION_RESULT_COPY_RENDERER,
    RenderedAcquisitionExplanation,
    explain_acquisition_result,
    render_acquisition_explanation,
)


def test_result_copy_renderer_marker_is_enabled() -> None:
    assert CANON_ADVISORY_ACQUISITION_RESULT_COPY_RENDERER is True


def test_result_copy_renderer_builds_human_text() -> None:
    result = FeasibilitySolver().solve(
        AcquisitionFeasibilityRequest(
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
    )

    rendered = render_acquisition_explanation(explain_acquisition_result(result))
    assert isinstance(rendered, RenderedAcquisitionExplanation)
    assert rendered.headline
    assert rendered.narrative
