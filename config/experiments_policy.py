from __future__ import annotations

from dataclasses import dataclass

CANON_COMPAT_SHIM = True

@dataclass(frozen=True)
class ExperimentResultEvaluationPolicy:
    zero_uplift_floor: float = 0.0
    control_below_minimum_reason: str = 'control sample size below minimum'
    treatment_below_minimum_reason: str = 'treatment sample size below minimum'
    negative_uplift_reason: str = 'negative uplift'
    not_significant_reason: str = 'result is not statistically significant'


@dataclass(frozen=True)
class ConservativeRolloutPolicyDefaults:
    zero_uplift_floor: float = 0.0


@dataclass(frozen=True)
class ExperimentResultExplanationPolicy:
    no_blocking_reasons_text: str = 'no blocking reasons'
    confidence_ceiling: float = 1.0
    uplift_precision_digits: int = 4


DEFAULT_EXPERIMENT_RESULT_EVALUATION_POLICY = ExperimentResultEvaluationPolicy()
DEFAULT_CONSERVATIVE_ROLLOUT_POLICY_DEFAULTS = ConservativeRolloutPolicyDefaults()
DEFAULT_EXPERIMENT_RESULT_EXPLANATION_POLICY = ExperimentResultExplanationPolicy()
