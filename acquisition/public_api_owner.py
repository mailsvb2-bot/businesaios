from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .feasibility_solver import AcquisitionFeasibilityRequest, AcquisitionFeasibilityResult, FeasibilitySolver

CANON_ACQUISITION_PUBLIC_API_OWNER = True

class AcquisitionSolver(Protocol):
    def solve(self, request: AcquisitionFeasibilityRequest) -> AcquisitionFeasibilityResult:
        ...

@dataclass(frozen=True, slots=True)
class AcquisitionPublicAPI:
    solver: AcquisitionSolver

    def evaluate(self, request: AcquisitionFeasibilityRequest) -> AcquisitionFeasibilityResult:
        return self.solver.solve(request)

def create_acquisition_public_api(*, solver: AcquisitionSolver | None = None) -> AcquisitionPublicAPI:
    return AcquisitionPublicAPI(solver=solver or FeasibilitySolver())

def evaluate_acquisition_plan(
    request: AcquisitionFeasibilityRequest,
    *,
    solver: AcquisitionSolver | None = None,
) -> AcquisitionFeasibilityResult:
    return create_acquisition_public_api(solver=solver).evaluate(request)

__all__ = [
    "AcquisitionPublicAPI",
    "AcquisitionSolver",
    "CANON_ACQUISITION_PUBLIC_API_OWNER",
    "create_acquisition_public_api",
    "evaluate_acquisition_plan",
]
