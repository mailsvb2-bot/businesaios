from __future__ import annotations

from runtime.economic_core.acquisition_bridge import (
    build_acquisition_truth_fragment,
    build_acquisition_truth_snapshot_from_client_outcome,
)


def test_acquisition_truth_fragment_projects_cost_without_revenue_double_count() -> None:
    snapshot = build_acquisition_truth_snapshot_from_client_outcome(truth_snapshot={
        "tenant_id": "tenant-a",
        "business_id": "biz-a",
        "order_id": "order-a",
        "acquisition_cost": 20.0,
        "cac": 20.0,
        "source_channel": "ads",
        "reconciliation_consistent": True,
    })
    fragment = build_acquisition_truth_fragment(acquisition_snapshot=snapshot)
    assert fragment.domain == "acquisition"
    assert fragment.aggregation_mode == "cost_primary"
    assert fragment.cost_total_minor == 2000
    assert fragment.unit_cost_minor == 2000
    assert fragment.booked_amount_minor is None
    assert fragment.corrected_amount_minor is None
