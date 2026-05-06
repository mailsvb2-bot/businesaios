from __future__ import annotations

import acquisition


def test_acquisition_package_exports_expected_public_surface() -> None:
    expected_names = {
        "AcquisitionFeasibilityRequest",
        "AcquisitionFeasibilityResult",
        "AcquisitionHeadlessEntrypoint",
        "AcquisitionPayloadError",
        "AcquisitionPublicAPI",
        "AcquisitionSolver",
        "BudgetOptimizer",
        "BudgetOptimizerInputs",
        "BudgetRecommendation",
        "CANON_ACQUISITION_BUDGET_OPTIMIZER",
        "CANON_ACQUISITION_CAC_MODEL",
        "CANON_ACQUISITION_FEASIBILITY_SOLVER",
        "CANON_ACQUISITION_FUNNEL_MODEL",
        "CANON_ACQUISITION_HEADLESS_ENTRYPOINT",
        "CANON_ACQUISITION_PUBLIC_API",
        "CANON_ACQUISITION_REQUEST_ADAPTER",
        "CANON_ACQUISITION_TIMELINE_ESTIMATOR",
        "CacInputs",
        "CacSnapshot",
        "CustomerAcquisitionCostModel",
        "FeasibilitySolver",
        "FunnelModel",
        "FunnelSnapshot",
        "FunnelStage",
        "TimelineEstimate",
        "TimelineEstimator",
        "TimelineEstimatorInputs",
        "create_acquisition_headless_entrypoint",
        "create_acquisition_public_api",
        "evaluate_acquisition_payload",
        "evaluate_acquisition_plan",
        "request_from_payload",
    }
    assert set(acquisition.__all__) == expected_names
    for name in expected_names:
        assert hasattr(acquisition, name), name
