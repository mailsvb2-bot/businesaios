from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Iterable, Mapping

from execution.optimization.feedback_pipeline import AdaptationObservation, FeedbackPipeline
from execution.optimization.noise_guard import FeedbackNoiseGuard
from execution.optimization.policy_adaptation_engine import PolicyAdaptationEngine
from execution.optimization.performance_profile_store import PerformanceProfile


@dataclass(frozen=True)
class ReplayReport:
    processed: int
    accepted: int
    rejected: int
    final_profile: PerformanceProfile
    runtime_policy_view: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            'processed': self.processed,
            'accepted': self.accepted,
            'rejected': self.rejected,
            'final_profile': self.final_profile.to_dict(),
            'runtime_policy_view': dict(self.runtime_policy_view),
        }


class OfflineReplaySimulator:
    def __init__(self, *, pipeline: FeedbackPipeline | None = None, noise_guard: FeedbackNoiseGuard | None = None, policy_engine: PolicyAdaptationEngine | None = None) -> None:
        self._pipeline = pipeline or FeedbackPipeline()
        self._noise_guard = noise_guard or FeedbackNoiseGuard()
        self._policy_engine = policy_engine or PolicyAdaptationEngine()

    def replay(self, *, profile: PerformanceProfile, historical_feedback: Iterable[Mapping[str, Any] | AdaptationObservation]) -> ReplayReport:
        current = profile
        memory = profile.noise_memory
        processed = accepted = rejected = 0
        for item in historical_feedback:
            processed += 1
            observation = item if isinstance(item, AdaptationObservation) else self._pipeline.normalize(feedback=item)
            verdict = self._noise_guard.evaluate(observation=observation.to_dict(), memory=memory)
            if not verdict.accepted:
                rejected += 1
                current = self._policy_engine.adapt_profile(current=current, accepted_observations=[], rejected_count=1, last_noise_reason=verdict.reason)
                continue
            accepted += 1
            self._noise_guard.commit(observation=observation.to_dict(), memory=memory)
            current = replace(current, noise_memory=memory)
            current = self._policy_engine.adapt_profile(current=current, accepted_observations=[observation], rejected_count=0, last_noise_reason='')
        current = replace(current, noise_memory=memory)
        return ReplayReport(processed, accepted, rejected, current, self._policy_engine.runtime_policy_view(profile=current))


__all__ = ['OfflineReplaySimulator', 'ReplayReport']
