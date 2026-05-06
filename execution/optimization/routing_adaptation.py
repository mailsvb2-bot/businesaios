from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from execution.optimization.adaptation_metrics import bounded_delta, clamp, ewma
from execution.optimization.feedback_pipeline import AdaptationObservation
from execution.optimization.performance_profile_store import RouteAdaptationState


class RoutingAdaptationEngine:
    def __init__(self, *, learning_rate: float = 0.18, max_weight_step: float = 0.10, min_samples_to_adapt: int = 5) -> None:
        self._learning_rate = max(0.01, min(1.0, learning_rate))
        self._max_weight_step = max(0.01, max_weight_step)
        self._min_samples_to_adapt = max(1, int(min_samples_to_adapt))

    @staticmethod
    def _quality_signal(item: AdaptationObservation) -> float:
        executed = 1.0 if item.executed else 0.0
        verified = 1.0 if item.verified else 0.0
        achieved = 1.0 if item.achieved else 0.0
        roi = clamp(item.roi_ratio / 2.0)
        return clamp((executed * 0.18) + (verified * 0.30) + (achieved * 0.27) + (roi * 0.25))

    def adapt_route(self, *, current: RouteAdaptationState | None, observations: Iterable[AdaptationObservation]) -> RouteAdaptationState:
        series = list(observations)
        base = current or RouteAdaptationState(route_key=series[-1].route_key if series else 'default')
        if not series:
            return base
        sample_count = base.sample_count
        success_rate = base.success_rate
        verification_rate = base.verification_rate
        roi_score = base.roi_score
        weight = base.weight
        for item in series:
            sample_count += 1
            success_rate = ewma(previous=success_rate, new_value=1.0 if item.executed else 0.0, alpha=self._learning_rate)
            verification_rate = ewma(previous=verification_rate, new_value=1.0 if item.verified else 0.0, alpha=self._learning_rate)
            roi_score = ewma(previous=roi_score, new_value=clamp(item.roi_ratio / 2.0), alpha=self._learning_rate)
            if sample_count >= self._min_samples_to_adapt:
                proposed = 0.35 + (self._quality_signal(item) * 1.45)
                weight = bounded_delta(weight, proposed, max_step=self._max_weight_step)
        return replace(base, route_key=series[-1].route_key, weight=max(0.05, min(2.50, weight)), success_rate=success_rate, verification_rate=verification_rate, roi_score=roi_score, sample_count=sample_count)

    def recommend_routing_table(self, *, routes: Iterable[RouteAdaptationState]) -> dict[str, float]:
        items = list(routes)
        if not items:
            return {'default': 1.0}
        total = sum(max(0.05, item.weight) for item in items)
        if total <= 0.0:
            return {item.route_key: 1.0 / len(items) for item in items}
        return {item.route_key: max(0.05, item.weight) / total for item in items}


__all__ = ['RoutingAdaptationEngine']
