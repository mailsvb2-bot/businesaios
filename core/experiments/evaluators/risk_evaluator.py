from __future__ import annotations

from config.risk_evaluation_policy import (
    DEFAULT_EXPERIMENT_RISK_POLICY,
    ExperimentRiskPolicy,
)
from core.experiments.enums import RiskLevel


class RiskEvaluator:
    def __init__(self, policy: ExperimentRiskPolicy = DEFAULT_EXPERIMENT_RISK_POLICY) -> None:
        self._policy = policy

    def evaluate(
        self,
        *,
        uplift: float,
        p_value: float,
        minimum_required_exposures: int,
        control_exposures: int,
        treatment_exposures: int,
    ) -> RiskLevel:
        if control_exposures < minimum_required_exposures:
            return RiskLevel(str(self._policy.insufficient_exposure_level))
        if treatment_exposures < minimum_required_exposures:
            return RiskLevel(str(self._policy.insufficient_exposure_level))
        if uplift < 0.0:
            return RiskLevel(str(self._policy.negative_uplift_level))
        if p_value >= float(self._policy.medium_p_value_threshold):
            return RiskLevel(str(self._policy.medium_level))
        if p_value < float(self._policy.low_p_value_threshold):
            if not bool(self._policy.require_positive_uplift_for_low_risk) or uplift > 0.0:
                return RiskLevel(str(self._policy.low_level))
        return RiskLevel(str(self._policy.medium_level))
