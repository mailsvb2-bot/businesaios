from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence


@dataclass(frozen=True)
class UpliftEstimate:
    treatment_mean: float
    control_mean: float
    uplift: float

def estimate_difference_in_means_uplift(
    treatment_outcomes: Sequence[float],
    control_outcomes: Sequence[float],
) -> UpliftEstimate:
    if not treatment_outcomes or not control_outcomes:
        raise ValueError("treatment_outcomes and control_outcomes must be non-empty")
    treatment_mean = sum(float(x) for x in treatment_outcomes) / len(treatment_outcomes)
    control_mean = sum(float(x) for x in control_outcomes) / len(control_outcomes)
    return UpliftEstimate(
        treatment_mean=treatment_mean,
        control_mean=control_mean,
        uplift=treatment_mean - control_mean,
    )
