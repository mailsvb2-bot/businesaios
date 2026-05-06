from __future__ import annotations

from config.creative_experiment_confidence_policy import (
    DEFAULT_CREATIVE_EXPERIMENT_CONFIDENCE_POLICY,
    CreativeExperimentConfidencePolicy,
)
from core.creative_intelligence.models import ExperimentConfidenceSnapshot
from core.experiments.types import EvaluationSummary


def _clamp_score(value: float, *, policy: CreativeExperimentConfidencePolicy) -> float:
    return max(float(policy.min_score), min(float(policy.max_score), float(value)))


def build_experiment_confidence_snapshot(
    *,
    creative_id: str,
    summary: EvaluationSummary | None,
    policy: CreativeExperimentConfidencePolicy | None = None,
) -> ExperimentConfidenceSnapshot:
    policy = policy or DEFAULT_CREATIVE_EXPERIMENT_CONFIDENCE_POLICY
    if summary is None:
        return ExperimentConfidenceSnapshot(
            creative_id=creative_id,
            uplift=float(policy.default_uplift),
            p_value=float(policy.default_p_value),
            confidence_score=float(policy.default_confidence_score),
            rollout_readiness=float(policy.default_rollout_readiness),
        )

    confidence = _clamp_score(
        float(policy.confidence_baseline) - float(summary.p_value),
        policy=policy,
    )
    uplift = float(summary.uplift)
    rollout_readiness = _clamp_score(
        (float(policy.confidence_weight) * confidence)
        + (float(policy.uplift_weight) * max(float(policy.min_score), uplift))
        + (float(policy.significance_bonus) if summary.significant else float(policy.default_rollout_readiness)),
        policy=policy,
    )
    return ExperimentConfidenceSnapshot(
        creative_id=creative_id,
        uplift=uplift,
        p_value=float(summary.p_value),
        confidence_score=confidence,
        rollout_readiness=rollout_readiness,
    )
