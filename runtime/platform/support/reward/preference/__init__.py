from __future__ import annotations

"""Canonical preference-reward surface with compat alias submodules."""

import math

class EvaluatorBridge:
    def bridge(self, score: float) -> dict[str, float]:
        return {"preference_score": score}

class PreferenceDatasetBuilder:
    def build(self, winning: list[str], losing: list[str]) -> list[tuple[str, str]]:
        return list(zip(winning, losing))

class PreferenceModel:
    def score(self, left: float, right: float) -> float:
        return left - right

class PreferencePairSampler:
    def sample(self, pairs: list[tuple[str, str]], n: int) -> list[tuple[str, str]]:
        return pairs[:n]

class PreferenceTrainer:
    def __init__(self, model: PreferenceModel) -> None:
        self._model = model

    def fit_step(self, preferred: float, rejected: float) -> float:
        return self._model.score(preferred, rejected)

def logistic_ranking_loss(score_delta: float) -> float:
    return math.log(1.0 + math.exp(-score_delta))

def reward_from_preference(score_delta: float) -> float:
    return float(score_delta)

_ALIAS_EXPORTS = {
    "evaluator_bridge": "EvaluatorBridge",
    "preference_dataset_builder": "PreferenceDatasetBuilder",
    "preference_model": "PreferenceModel",
    "preference_pair_sampler": "PreferencePairSampler",
    "preference_trainer": "PreferenceTrainer",
    "ranking_loss": "logistic_ranking_loss",
    "reward_from_preferences": "reward_from_preference",
}

__all__ = [
    "EvaluatorBridge",
    "PreferenceDatasetBuilder",
    "PreferenceModel",
    "PreferencePairSampler",
    "PreferenceTrainer",
    "logistic_ranking_loss",
    "reward_from_preference",
] + list(_ALIAS_EXPORTS)
