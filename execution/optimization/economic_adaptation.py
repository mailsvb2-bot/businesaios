from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from execution.optimization.adaptation_metrics import bounded_delta, clamp, ewma
from execution.optimization.feedback_pipeline import AdaptationObservation
from execution.optimization.performance_profile_store import EconomicAdaptationState


class EconomicAdaptationEngine:
    def __init__(self, *, learning_rate: float = 0.12, max_budget_step: float = 0.08, min_samples_to_adapt: int = 5) -> None:
        self._learning_rate = max(0.01, min(1.0, learning_rate))
        self._max_budget_step = max(0.01, max_budget_step)
        self._min_samples_to_adapt = max(1, int(min_samples_to_adapt))

    def adapt(self, *, current: EconomicAdaptationState, observations: Iterable[AdaptationObservation]) -> EconomicAdaptationState:
        series = list(observations)
        if not series:
            return current
        roi_signal = current.min_expected_roi
        spend_tightness = current.spend_tightness
        budget_multiplier = current.budget_multiplier
        roi_gate = current.min_expected_roi
        seen = 0
        for item in series:
            seen += 1
            achieved_signal = 1.0 if item.achieved else 0.0
            verified_signal = 1.0 if item.verified else 0.0
            normalized_roi = min(5.0, item.roi_ratio)
            roi_signal = ewma(previous=roi_signal, new_value=normalized_roi, alpha=self._learning_rate)
            spend_tightness = ewma(previous=spend_tightness, new_value=1.0 - ((achieved_signal * 0.55) + (verified_signal * 0.45)), alpha=self._learning_rate)
            if seen < self._min_samples_to_adapt:
                continue
            if item.verified and item.achieved and item.roi_ratio >= roi_gate:
                proposed = budget_multiplier + 0.06
            elif (not item.verified) or item.roi_ratio < roi_gate:
                proposed = budget_multiplier - 0.06
            else:
                proposed = budget_multiplier
            budget_multiplier = bounded_delta(budget_multiplier, proposed, max_step=self._max_budget_step)
        return replace(current, budget_multiplier=max(0.25, min(3.0, budget_multiplier)), spend_tightness=clamp(spend_tightness), min_expected_roi=max(0.05, min(5.0, roi_signal)))


__all__ = ['EconomicAdaptationEngine']
