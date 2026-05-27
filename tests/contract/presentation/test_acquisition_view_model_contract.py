from __future__ import annotations

from acquisition import evaluate_acquisition_payload
from presentation import (
    CANON_PRESENTATION_ACQUISITION_VIEW_MODEL,
    AcquisitionRecommendationView,
    AcquisitionViewModel,
    build_acquisition_view_model,
)


def _payload() -> dict[str, object]:
    return {
        'target_customers': 120,
        'total_budget': 50.0,
        'daily_budget': 50.0,
        'cost_per_entry': 1.0,
        'gross_margin_ltv': 200.0,
        'target_days': 3.0,
        'expected_monthly_margin_per_customer': 20.0,
        'stages': (
            {'name': 'traffic_to_lead', 'conversion_rate': 0.2, 'avg_stage_days': 3.0, 'touchpoints': 1},
            {'name': 'lead_to_meeting', 'conversion_rate': 0.5, 'avg_stage_days': 4.0, 'touchpoints': 2},
            {'name': 'meeting_to_sale', 'conversion_rate': 0.5, 'avg_stage_days': 7.0, 'touchpoints': 3},
        ),
    }


def test_view_model_contract() -> None:
    assert CANON_PRESENTATION_ACQUISITION_VIEW_MODEL is True
    result = evaluate_acquisition_payload(_payload())
    vm = build_acquisition_view_model(result)
    assert isinstance(vm, AcquisitionViewModel)
    assert isinstance(vm.recommendations, tuple)
    if vm.recommendations:
        assert isinstance(vm.recommendations[0], AcquisitionRecommendationView)
