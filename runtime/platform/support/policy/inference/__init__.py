"""Canonical policy inference surface with compat alias submodules."""

from __future__ import annotations


from dataclasses import dataclass
from typing import Any

from runtime.platform.support.contracts.observation import Observation


class ActionPostprocessing:
    def apply(self, action):
        return action

class ActionSampler:
    def sample(self, actions):
        if not actions:
            raise ValueError("No actions to sample")
        return actions[0]

class BatchInference:
    def __init__(self, engine) -> None:
        self._engine = engine

    def run(self, observations):
        return [self._engine.infer(observation) for observation in observations]

class DeterministicInference:
    def __init__(self, policy) -> None:
        self._policy = policy

    def infer(self, observation):
        return self._policy.act(observation)

class InferenceCaching:
    def __init__(self) -> None:
        self._cache: dict[str, Any] = {}

    def get(self, key: str) -> Any | None:
        return self._cache.get(key)

    def set(self, key: str, value: Any) -> None:
        self._cache[key] = value

class InferenceEngine:
    def __init__(self, policy) -> None:
        self._policy = policy

    def infer(self, observation: Observation):
        return self._policy.act(observation)

@dataclass(frozen=True)
class LatencyBudget:
    max_latency_ms: int

class StochasticInference:
    def __init__(self, policy) -> None:
        self._policy = policy

    def infer(self, observation):
        return self._policy.act(observation)

class StreamingInference:
    def __init__(self, engine) -> None:
        self._engine = engine

    def run(self, observations):
        for observation in observations:
            yield self._engine.infer(observation)

_ALIAS_EXPORTS = {
    "action_postprocessing": "ActionPostprocessing",
    "action_sampler": "ActionSampler",
    "batch_inference": "BatchInference",
    "deterministic_inference": "DeterministicInference",
    "inference_caching": "InferenceCaching",
    "inference_engine": "InferenceEngine",
    "latency_budgeting": "LatencyBudget",
    "stochastic_inference": "StochasticInference",
    "streaming_inference": "StreamingInference",
}

__all__ = [
    "ActionPostprocessing",
    "ActionSampler",
    "BatchInference",
    "DeterministicInference",
    "InferenceCaching",
    "InferenceEngine",
    "LatencyBudget",
    "StochasticInference",
    "StreamingInference",
] + list(_ALIAS_EXPORTS)
