from __future__ import annotations

from core.experiments.types import ExperimentResult


class UpliftEvaluator:
    def evaluate(
        self,
        *,
        control_conversions: int,
        control_exposures: int,
        treatment_conversions: int,
        treatment_exposures: int,
    ) -> float:
        if control_exposures <= 0 or treatment_exposures <= 0:
            return 0.0

        control_rate = control_conversions / control_exposures
        treatment_rate = treatment_conversions / treatment_exposures
        if control_rate == 0.0:
            return treatment_rate
        return (treatment_rate - control_rate) / control_rate


def evaluate_uplift(result: ExperimentResult) -> float:
    return float(result.uplift)
