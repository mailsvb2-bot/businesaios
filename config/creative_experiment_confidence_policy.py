from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass


@dataclass(frozen=True)
class CreativeExperimentConfidencePolicy:
    default_uplift: float = 0.0
    default_p_value: float = 1.0
    default_confidence_score: float = 0.0
    default_rollout_readiness: float = 0.0
    confidence_baseline: float = 1.0
    confidence_weight: float = 0.50
    uplift_weight: float = 0.35
    significance_bonus: float = 0.15
    min_score: float = 0.0
    max_score: float = 1.0


DEFAULT_CREATIVE_EXPERIMENT_CONFIDENCE_POLICY = CreativeExperimentConfidencePolicy()
