from __future__ import annotations

from acquisition import evaluate_acquisition_payload
from advisory import (
    CANON_ADVISORY_ACQUISITION_RECOMMENDATION_BUILDER,
    CANON_ADVISORY_ACQUISITION_RESULT_PROJECTION,
    AcquisitionExplanation,
    AcquisitionRecommendation,
    build_acquisition_recommendations,
    explain_acquisition_result,
)


def _payload() -> dict[str, object]:
    return {
        "target_customers": 10,
        "total_budget": 2200.0,
        "daily_budget": 200.0,
        "cost_per_entry": 10.0,
        "gross_margin_ltv": 1000.0,
        "stages": [
            {"name": "traffic_to_lead", "conversion_rate": 0.2, "avg_stage_days": 3.0, "touchpoints": 1},
            {"name": "lead_to_meeting", "conversion_rate": 0.5, "avg_stage_days": 4.0, "touchpoints": 2},
            {"name": "meeting_to_sale", "conversion_rate": 0.5, "avg_stage_days": 7.0, "touchpoints": 3},
        ],
        "target_days": 20.0,
        "setup_cost": 100.0,
        "expected_monthly_margin_per_customer": 100.0,
    }


def test_explainability_contract_markers_are_enabled() -> None:
    assert CANON_ADVISORY_ACQUISITION_RESULT_PROJECTION is True
    assert CANON_ADVISORY_ACQUISITION_RECOMMENDATION_BUILDER is True


def test_explainability_contract_produces_projection_and_recommendations() -> None:
    result = evaluate_acquisition_payload(_payload())
    explanation = explain_acquisition_result(result)
    recommendations = build_acquisition_recommendations(result)

    assert isinstance(explanation, AcquisitionExplanation)
    assert explanation.primary_constraint
    assert recommendations.items
    assert isinstance(recommendations.items[0], AcquisitionRecommendation)
