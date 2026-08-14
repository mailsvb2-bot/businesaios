from __future__ import annotations

from canon.public_api_alias import install_public_api_alias

from .budget_optimizer import (
    CANON_ACQUISITION_BUDGET_OPTIMIZER,
    BudgetOptimizer,
    BudgetOptimizerInputs,
    BudgetRecommendation,
)
from .cac_model import (
    CANON_ACQUISITION_CAC_MODEL,
    CacInputs,
    CacSnapshot,
    CustomerAcquisitionCostModel,
)
from .feasibility_solver import (
    CANON_ACQUISITION_FEASIBILITY_SOLVER,
    AcquisitionFeasibilityRequest,
    AcquisitionFeasibilityResult,
    FeasibilitySolver,
)
from .funnel_model import (
    CANON_ACQUISITION_FUNNEL_MODEL,
    FunnelModel,
    FunnelSnapshot,
    FunnelStage,
)
from .headless_entrypoint import (
    CANON_ACQUISITION_HEADLESS_ENTRYPOINT,
    AcquisitionHeadlessEntrypoint,
    create_acquisition_headless_entrypoint,
    evaluate_acquisition_payload,
)
from .public_api_owner import (
    CANON_ACQUISITION_PUBLIC_API_OWNER as CANON_ACQUISITION_PUBLIC_API_OWNER,
)
from .public_api_owner import (
    AcquisitionPublicAPI,
    AcquisitionSolver,
    create_acquisition_public_api,
    evaluate_acquisition_plan,
)
from .request_adapter import (
    CANON_ACQUISITION_REQUEST_ADAPTER,
    AcquisitionPayloadError,
    request_from_payload,
)
from .timeline_estimator import (
    CANON_ACQUISITION_TIMELINE_ESTIMATOR,
    TimelineEstimate,
    TimelineEstimator,
    TimelineEstimatorInputs,
)

CANON_ACQUISITION_PUBLIC_API = True

install_public_api_alias(__name__)

__all__ = [
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
]
