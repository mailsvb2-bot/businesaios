from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from acquisition import (
    AcquisitionFeasibilityRequest,
    AcquisitionFeasibilityResult,
    AcquisitionPublicAPI,
    create_acquisition_public_api,
    request_from_payload,
)

CANON_ACQUISITION_HEADLESS_ENTRYPOINT = True


@dataclass(frozen=True, slots=True)
class AcquisitionHeadlessEntrypoint:
    """
    Thin headless boundary for acquisition evaluation.

    The boundary is intentionally narrow:
    payload -> canonical request -> public API -> solver

    Important:
    - no feasibility math here
    - no duplicate decision logic here
    - no UI coupling here
    """

    api: AcquisitionPublicAPI

    def evaluate(
        self,
        payload: Mapping[str, Any] | AcquisitionFeasibilityRequest,
    ) -> AcquisitionFeasibilityResult:
        request = request_from_payload(payload)
        return self.api.evaluate(request)


def create_acquisition_headless_entrypoint(
    api: AcquisitionPublicAPI | None = None,
) -> AcquisitionHeadlessEntrypoint:
    return AcquisitionHeadlessEntrypoint(api=api or create_acquisition_public_api())


def evaluate_acquisition_payload(
    payload: Mapping[str, Any] | AcquisitionFeasibilityRequest,
    *,
    api: AcquisitionPublicAPI | None = None,
) -> AcquisitionFeasibilityResult:
    return create_acquisition_headless_entrypoint(api=api).evaluate(payload)


__all__ = [
    "AcquisitionHeadlessEntrypoint",
    "CANON_ACQUISITION_HEADLESS_ENTRYPOINT",
    "create_acquisition_headless_entrypoint",
    "evaluate_acquisition_payload",
]
