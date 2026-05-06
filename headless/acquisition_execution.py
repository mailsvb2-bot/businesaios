from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from acquisition import AcquisitionHeadlessEntrypoint, create_acquisition_headless_entrypoint
from acquisition import AcquisitionFeasibilityRequest
from presentation import AcquisitionViewModel, build_acquisition_view_model


CANON_HEADLESS_ACQUISITION_EXECUTION = True


@dataclass(frozen=True, slots=True)
class HeadlessAcquisitionExecution:
    """Canonical headless boundary for acquisition calculations.

    Important:
    - no duplicated acquisition math
    - no parallel decision logic
    - no UI rendering side effects
    """

    entrypoint: AcquisitionHeadlessEntrypoint

    def execute(self, payload: Mapping[str, Any] | AcquisitionFeasibilityRequest) -> AcquisitionViewModel:
        return build_acquisition_view_model(self.entrypoint.evaluate(payload))


def create_headless_acquisition_execution(
    *,
    entrypoint: AcquisitionHeadlessEntrypoint | None = None,
) -> HeadlessAcquisitionExecution:
    return HeadlessAcquisitionExecution(entrypoint=entrypoint or create_acquisition_headless_entrypoint())


def execute_headless_acquisition(
    payload: Mapping[str, Any] | AcquisitionFeasibilityRequest,
    *,
    entrypoint: AcquisitionHeadlessEntrypoint | None = None,
) -> AcquisitionViewModel:
    return create_headless_acquisition_execution(entrypoint=entrypoint).execute(payload)


__all__ = [
    'CANON_HEADLESS_ACQUISITION_EXECUTION',
    'HeadlessAcquisitionExecution',
    'create_headless_acquisition_execution',
    'execute_headless_acquisition',
]
