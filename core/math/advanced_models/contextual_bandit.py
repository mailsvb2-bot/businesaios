from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Sequence

from .common import require_non_empty


def _feature_vector(context: Mapping[str, float], keys: Sequence[str]) -> list[float]:
    return [float(context.get(k, 0.0)) for k in keys]

@dataclass
class _ArmState:
    precision_diag: list[float]
    reward_weight: list[float]

@dataclass
class LinearThompsonBandit:
    feature_dim: int
    actions: Sequence[str]
    feature_keys: Sequence[str] | None = None
    alpha: float = 1.0
    random_seed: int = 7
    _rng: random.Random = field(init=False, repr=False)
    _arms: dict[str, _ArmState] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        require_non_empty("actions", list(self.actions))
        if self.feature_dim <= 0:
            raise ValueError("feature_dim must be positive")
        self._rng = random.Random(self.random_seed)
        self._arms = {
            action: _ArmState(
                precision_diag=[1.0 for _ in range(self.feature_dim)],
                reward_weight=[0.0 for _ in range(self.feature_dim)],
            )
            for action in self.actions
        }

    def select_action(self, context: Mapping[str, float]) -> str:
        if self.feature_keys is not None:
            x = _feature_vector(context, self.feature_keys)
        else:
            vals = [float(v) for _, v in sorted(context.items())][: self.feature_dim]
            x = vals + [0.0] * (self.feature_dim - len(vals))
        best_action = None
        best_sample = -math.inf
        for action, state in self._arms.items():
            sampled_theta = []
            for i in range(self.feature_dim):
                mean = state.reward_weight[i] / state.precision_diag[i]
                std = self.alpha / math.sqrt(state.precision_diag[i])
                sampled_theta.append(self._rng.gauss(mean, std))
            score = sum(w * xi for w, xi in zip(sampled_theta, x, strict=False))
            if score > best_sample:
                best_sample = score
                best_action = action
        assert best_action is not None
        return best_action

    def update(self, action: str, context: Mapping[str, float], reward: float) -> None:
        if action not in self._arms:
            raise KeyError(f"unknown action: {action}")
        if self.feature_keys is not None:
            x = _feature_vector(context, self.feature_keys)
        else:
            vals = [float(v) for _, v in sorted(context.items())][: self.feature_dim]
            x = vals + [0.0] * (self.feature_dim - len(vals))
        state = self._arms[action]
        for i, xi in enumerate(x):
            state.precision_diag[i] += xi * xi
            state.reward_weight[i] += reward * xi
