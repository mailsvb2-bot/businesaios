from __future__ import annotations

from headless import (
    CANON_HEADLESS_ACQUISITION_EXECUTION,
    HeadlessAcquisitionExecution,
    create_headless_acquisition_execution,
    execute_headless_acquisition,
)
from presentation import AcquisitionViewModel


def _payload() -> dict[str, object]:
    return {
        'target_customers': 10,
        'total_budget': 2200.0,
        'daily_budget': 200.0,
        'cost_per_entry': 10.0,
        'gross_margin_ltv': 1000.0,
        'target_days': 20.0,
        'setup_cost': 100.0,
        'max_cac_to_ltv_ratio': 0.33,
        'payback_horizon_months': 12.0,
        'expected_monthly_margin_per_customer': 100.0,
        'stages': (
            {'name': 'traffic_to_lead', 'conversion_rate': 0.2, 'avg_stage_days': 3.0, 'touchpoints': 1},
            {'name': 'lead_to_meeting', 'conversion_rate': 0.5, 'avg_stage_days': 4.0, 'touchpoints': 2},
            {'name': 'meeting_to_sale', 'conversion_rate': 0.5, 'avg_stage_days': 7.0, 'touchpoints': 3},
        ),
    }


def test_headless_public_api_contract() -> None:
    assert CANON_HEADLESS_ACQUISITION_EXECUTION is True
    execution = create_headless_acquisition_execution()
    assert isinstance(execution, HeadlessAcquisitionExecution)
    assert isinstance(execute_headless_acquisition(_payload(), entrypoint=execution.entrypoint), AcquisitionViewModel)
