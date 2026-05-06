from __future__ import annotations

from config.risk_evaluation_policy import (
    DEFAULT_INCREMENTALITY_POLICY,
    IncrementalityPolicy,
)
from core.causal.types import CausalResult
from core.creative_intelligence.models import IncrementalitySnapshot


def _clamp_score(value: float, *, policy: IncrementalityPolicy) -> float:
    return max(float(policy.minimum_score), min(float(policy.maximum_score), float(value)))


def _confidence_from_causal(
    result: CausalResult | None,
    *,
    policy: IncrementalityPolicy = DEFAULT_INCREMENTALITY_POLICY,
) -> float:
    if result is None:
        return float(policy.minimum_score)
    estimate = result.estimate
    if estimate.stderr is None:
        return float(policy.missing_stderr_confidence_fallback)
    width = 0.0
    if estimate.ci95_low is not None and estimate.ci95_high is not None:
        width = max(0.0, estimate.ci95_high - estimate.ci95_low)
    confidence = 1.0 / (1.0 + float(estimate.stderr) + width)
    return _clamp_score(confidence, policy=policy)


def build_incrementality_snapshot(
    *,
    creative_id: str,
    result: CausalResult | None,
    policy: IncrementalityPolicy = DEFAULT_INCREMENTALITY_POLICY,
) -> IncrementalitySnapshot:
    if result is None:
        return IncrementalitySnapshot(
            creative_id=creative_id,
            estimated_effect=0.0,
            confidence_score=0.0,
            downside_risk=1.0,
            method="none",
        )
    confidence = _confidence_from_causal(result, policy=policy)
    effect = float(result.estimate.effect)
    if effect >= 0.0:
        downside_risk = 1.0 - (float(policy.downside_confidence_weight) * confidence)
    else:
        negative_effect_component = min(float(policy.maximum_score), abs(effect) * float(policy.negative_effect_multiplier))
        downside_risk = negative_effect_component + (float(policy.downside_confidence_weight) * (1.0 - confidence))
    downside_risk = _clamp_score(downside_risk, policy=policy)
    return IncrementalitySnapshot(
        creative_id=creative_id,
        estimated_effect=effect,
        confidence_score=confidence,
        downside_risk=downside_risk,
        method=str(result.trace.get("method") or result.estimate.method or "unknown"),
    )
