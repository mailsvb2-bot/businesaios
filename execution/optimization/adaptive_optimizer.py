from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any
from collections.abc import Iterable, Mapping

from execution.optimization.feedback_pipeline import AdaptationObservation, FeedbackPipeline
from execution.optimization.noise_guard import FeedbackNoiseGuard, NoiseMemory
from execution.optimization.offline_replay_simulator import OfflineReplaySimulator
from execution.optimization.policy_adaptation_engine import PolicyAdaptationEngine
from execution.optimization.performance_profile_store import FilePerformanceProfileStore, PerformanceProfile


@dataclass(frozen=True)
class AdaptiveOptimizationResult:
    accepted: bool
    noise_reason: str
    profile: PerformanceProfile
    runtime_policy_view: dict[str, Any]
    observation: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            'accepted': self.accepted,
            'noise_reason': self.noise_reason,
            'profile': self.profile.to_dict(),
            'runtime_policy_view': dict(self.runtime_policy_view),
            'observation': dict(self.observation),
        }


class AdaptiveOptimizer:
    def __init__(self, *, store: FilePerformanceProfileStore, pipeline: FeedbackPipeline | None = None, noise_guard: FeedbackNoiseGuard | None = None, policy_engine: PolicyAdaptationEngine | None = None, replay_simulator: OfflineReplaySimulator | None = None) -> None:
        self._store = store
        self._pipeline = pipeline or FeedbackPipeline()
        self._noise_guard = noise_guard or FeedbackNoiseGuard()
        self._policy_engine = policy_engine or PolicyAdaptationEngine()
        self._replay_simulator = replay_simulator or OfflineReplaySimulator(pipeline=self._pipeline, noise_guard=self._noise_guard, policy_engine=self._policy_engine)
        self._noise_memory: dict[str, NoiseMemory] = {}

    @staticmethod
    def _memory_key(*, tenant_id: str, business_id: str, capability_key: str) -> str:
        return f'{tenant_id}::{business_id}::{capability_key}'

    def _get_memory(self, *, profile: PerformanceProfile) -> NoiseMemory:
        key = self._memory_key(tenant_id=profile.tenant_id, business_id=profile.business_id, capability_key=profile.capability_key)
        memory = self._noise_memory.get(key)
        if memory is None:
            memory = profile.noise_memory
            self._noise_memory[key] = memory
        return memory

    def load_runtime_policy(self, *, tenant_id: str, business_id: str, capability_key: str) -> dict[str, Any]:
        profile = self._store.load(tenant_id=tenant_id, business_id=business_id, capability_key=capability_key)
        return self._policy_engine.runtime_policy_view(profile=profile)

    def update_from_feedback(self, *, feedback: Mapping[str, Any] | AdaptationObservation) -> AdaptiveOptimizationResult:
        observation = feedback if isinstance(feedback, AdaptationObservation) else self._pipeline.normalize(feedback=feedback)
        profile = self._store.load(tenant_id=observation.tenant_id, business_id=observation.business_id, capability_key=observation.capability_key)
        if not observation.identity_complete:
            profile = self._policy_engine.adapt_profile(current=profile, accepted_observations=[], rejected_count=1, last_noise_reason='invalid_identity')
            self._store.save(profile)
            return AdaptiveOptimizationResult(False, 'invalid_identity', profile, self._policy_engine.runtime_policy_view(profile=profile), observation.to_dict())
        memory = self._get_memory(profile=profile)
        verdict = self._noise_guard.evaluate(observation=observation.to_dict(), memory=memory)
        if verdict.accepted:
            self._noise_guard.commit(observation=observation.to_dict(), memory=memory)
            profile = replace(profile, noise_memory=memory)
            profile = self._policy_engine.adapt_profile(current=profile, accepted_observations=[observation], rejected_count=0, last_noise_reason='')
        else:
            profile = replace(profile, noise_memory=memory)
            profile = self._policy_engine.adapt_profile(current=profile, accepted_observations=[], rejected_count=1, last_noise_reason=verdict.reason)
        profile = replace(profile, noise_memory=memory)
        self._store.save(profile)
        return AdaptiveOptimizationResult(verdict.accepted, verdict.reason, profile, self._policy_engine.runtime_policy_view(profile=profile), observation.to_dict())

    def replay_history(self, *, tenant_id: str, business_id: str, capability_key: str, historical_feedback: Iterable[Mapping[str, Any] | AdaptationObservation]) -> dict[str, Any]:
        profile = self._store.load(tenant_id=tenant_id, business_id=business_id, capability_key=capability_key)
        report = self._replay_simulator.replay(profile=profile, historical_feedback=historical_feedback)
        self._store.save(report.final_profile)
        return report.to_dict()


__all__ = ['AdaptiveOptimizationResult', 'AdaptiveOptimizer']
