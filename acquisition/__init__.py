from __future__ import annotations

from dataclasses import dataclass

from canon.public_api_alias import install_public_api_alias
from typing import Protocol


from .budget_optimizer import (
    BudgetOptimizer,
    BudgetOptimizerInputs,
    BudgetRecommendation,
    CANON_ACQUISITION_BUDGET_OPTIMIZER,
)
from .cac_model import (
    CacInputs,
    CacSnapshot,
    CustomerAcquisitionCostModel,
    CANON_ACQUISITION_CAC_MODEL,
)
from .feasibility_solver import (
    AcquisitionFeasibilityRequest,
    AcquisitionFeasibilityResult,
    CANON_ACQUISITION_FEASIBILITY_SOLVER,
    FeasibilitySolver,
)
from .funnel_model import (
    FunnelModel,
    FunnelSnapshot,
    FunnelStage,
    CANON_ACQUISITION_FUNNEL_MODEL,
)
from .request_adapter import (
    AcquisitionPayloadError,
    CANON_ACQUISITION_REQUEST_ADAPTER,
    request_from_payload,
)
from .timeline_estimator import (
    TimelineEstimate,
    TimelineEstimator,
    TimelineEstimatorInputs,
    CANON_ACQUISITION_TIMELINE_ESTIMATOR,
)

CANON_ACQUISITION_PUBLIC_API = True


class AcquisitionSolver(Protocol):
    def solve(self, request: AcquisitionFeasibilityRequest) -> AcquisitionFeasibilityResult:
        ...


@dataclass(frozen=True, slots=True)
class AcquisitionPublicAPI:
    solver: AcquisitionSolver

    def evaluate(self, request: AcquisitionFeasibilityRequest) -> AcquisitionFeasibilityResult:
        return self.solver.solve(request)


def create_acquisition_public_api(
    *,
    solver: AcquisitionSolver | None = None,
) -> AcquisitionPublicAPI:
    return AcquisitionPublicAPI(solver=solver or FeasibilitySolver())


def evaluate_acquisition_plan(
    request: AcquisitionFeasibilityRequest,
    *,
    solver: AcquisitionSolver | None = None,
) -> AcquisitionFeasibilityResult:
    return create_acquisition_public_api(solver=solver).evaluate(request)


from .headless_entrypoint import (
    AcquisitionHeadlessEntrypoint,
    CANON_ACQUISITION_HEADLESS_ENTRYPOINT,
    create_acquisition_headless_entrypoint,
    evaluate_acquisition_payload,
)

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
