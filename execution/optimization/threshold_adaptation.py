from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from execution.optimization.adaptation_metrics import bounded_delta, clamp, ewma
from execution.optimization.feedback_pipeline import AdaptationObservation
from execution.optimization.performance_profile_store import ThresholdAdaptationState


class ThresholdAdaptationEngine:
    def __init__(self, *, learning_rate: float = 0.10, max_step: float = 0.03, min_samples_to_adapt: int = 5) -> None:
        self._learning_rate = max(0.01, min(1.0, learning_rate))
        self._max_step = max(0.01, max_step)
        self._min_samples_to_adapt = max(1, int(min_samples_to_adapt))

    def adapt(self, *, current: ThresholdAdaptationState, observations: Iterable[AdaptationObservation]) -> ThresholdAdaptationState:
        series = list(observations)
        if not series:
            return current
        verification_threshold = current.verification_threshold
        escalation_threshold = current.escalation_threshold
        retry_threshold = current.retry_threshold
        seen = 0
        for item in series:
            seen += 1
            if seen < self._min_samples_to_adapt:
                continue
            if item.verified and item.achieved:
                target_v = 0.56
            elif item.verified and not item.achieved:
                target_v = 0.60
            else:
                target_v = clamp(0.64 + ((1.0 - item.verification_confidence) * 0.18), 0.60, 0.88)
            verification_threshold = bounded_delta(verification_threshold, ewma(previous=verification_threshold, new_value=target_v, alpha=self._learning_rate), max_step=self._max_step)
            target_e = 0.54 if (not item.executed or not item.verified) else 0.40 if (item.executed and item.verified and not item.achieved) else 0.26
            escalation_threshold = bounded_delta(escalation_threshold, ewma(previous=escalation_threshold, new_value=target_e, alpha=self._learning_rate), max_step=self._max_step)
            target_r = 0.70 if (item.executed and not item.verified) else 0.60 if not item.executed else 0.45
            retry_threshold = bounded_delta(retry_threshold, ewma(previous=retry_threshold, new_value=target_r, alpha=self._learning_rate), max_step=self._max_step)
        return replace(current, verification_threshold=clamp(verification_threshold), escalation_threshold=clamp(escalation_threshold), retry_threshold=clamp(retry_threshold))


__all__ = ['ThresholdAdaptationEngine']
