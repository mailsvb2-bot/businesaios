from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from collections.abc import Iterable, Sequence
from config.scoring_behavior_policy import DEFAULT_ADAPTATION_METRICS_POLICY


ADAPTATION_METRICS_SCHEMA_VERSION = 2


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    if low > high:
        low, high = high, low
    if value < low:
        return low
    if value > high:
        return high
    return value


def safe_float(value: object, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def safe_int(value: object, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def ewma(*, previous: float, new_value: float, alpha: float) -> float:
    alpha = clamp(alpha, 0.0, 1.0)
    return (previous * (1.0 - alpha)) + (new_value * alpha)


def weighted_mean(values: Sequence[float], weights: Sequence[float]) -> float:
    if not values or not weights or len(values) != len(weights):
        return 0.0
    total_weight = sum(max(0.0, safe_float(weight)) for weight in weights)
    if total_weight <= 0.0:
        return 0.0
    weighted_sum = sum(safe_float(v) * max(0.0, safe_float(w)) for v, w in zip(values, weights))
    return weighted_sum / total_weight


def sample_stddev(values: Sequence[float]) -> float:
    if len(values) <= 1:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return sqrt(max(0.0, variance))


def confidence_from_volume(sample_count: int, *, saturation: int | None = None) -> float:
    if sample_count <= 0:
        return 0.0
    policy = DEFAULT_ADAPTATION_METRICS_POLICY
    saturation = policy.confidence_volume_saturation if saturation is None else saturation
    saturation = max(1, int(saturation))
    return clamp(sample_count / saturation)


def bounded_delta(current: float, proposed: float, *, max_step: float) -> float:
    max_step = abs(max_step)
    delta = proposed - current
    if delta > max_step:
        return current + max_step
    if delta < -max_step:
        return current - max_step
    return proposed


def streak_direction(values: Iterable[float]) -> int:
    series = list(values)
    if len(series) <= 1:
        return 0
    positive = 0
    negative = 0
    for idx in range(1, len(series)):
        delta = series[idx] - series[idx - 1]
        if delta > 0:
            positive += 1
        elif delta < 0:
            negative += 1
    if positive > negative:
        return 1
    if negative > positive:
        return -1
    return 0


@dataclass(frozen=True)
class AdaptationScorecard:
    sample_count: int
    success_rate: float
    verification_rate: float
    roi_score: float
    latency_score: float
    stability_score: float
    confidence: float

    @property
    def composite_score(self) -> float:
        policy = DEFAULT_ADAPTATION_METRICS_POLICY
        return clamp(
            (self.success_rate * policy.weight_success_rate)
            + (self.verification_rate * policy.weight_verification_rate)
            + (self.roi_score * policy.weight_roi_score)
            + (self.latency_score * policy.weight_latency_score)
            + (self.stability_score * policy.weight_stability_score)
        )


def build_scorecard(*, sample_count: int, success_rate: float, verification_rate: float, roi_score: float, latency_score: float, stability_score: float) -> AdaptationScorecard:
    return AdaptationScorecard(
        sample_count=max(0, int(sample_count)),
        success_rate=clamp(success_rate),
        verification_rate=clamp(verification_rate),
        roi_score=clamp(roi_score),
        latency_score=clamp(latency_score),
        stability_score=clamp(stability_score),
        confidence=confidence_from_volume(max(0, int(sample_count))),
    )


__all__ = [
    'ADAPTATION_METRICS_SCHEMA_VERSION',
    'AdaptationScorecard',
    'build_scorecard',
    'bounded_delta',
    'clamp',
    'confidence_from_volume',
    'ewma',
    'safe_float',
    'safe_int',
    'sample_stddev',
    'streak_direction',
    'weighted_mean',
]
