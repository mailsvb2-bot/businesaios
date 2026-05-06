from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class ArmStats:
    pulls: int = 0
    reward_sum: float = 0.0

    @property
    def mean(self) -> float:
        if self.pulls <= 0:
            return 0.0
        return self.reward_sum / self.pulls


class UCB1:
    """UCB1:
      score_i = μ_i + sqrt( 2 ln(n) / n_i )
    """

    def __init__(self, arms: List[str]):
        if not arms:
            raise ValueError("arms must be non-empty.")
        self.arms = list(arms)
        self.stats: Dict[str, ArmStats] = {a: ArmStats() for a in self.arms}
        self.total_pulls: int = 0

    def choose_arm(self) -> str:
        for a in self.arms:
            if self.stats[a].pulls == 0:
                return a
        n = max(1, self.total_pulls)
        best_a = self.arms[0]
        best_score = -1e18
        for a in self.arms:
            st = self.stats[a]
            bonus = math.sqrt((2.0 * math.log(n)) / st.pulls)
            score = st.mean + bonus
            if score > best_score:
                best_score = score
                best_a = a
        return best_a


    select = choose_arm
    def update(self, arm: str, reward: float) -> None:
        if arm not in self.stats:
            raise KeyError(f"Unknown arm: {arm}")
        r = float(reward)
        self.stats[arm].pulls += 1
        self.stats[arm].reward_sum += r
        self.total_pulls += 1


class ThompsonBernoulli:
    """Thompson sampling for Bernoulli rewards using Beta(α, β)."""

    def __init__(self, arms: List[str], *, alpha0: float = 1.0, beta0: float = 1.0):
        if not arms:
            raise ValueError("arms must be non-empty.")
        if alpha0 <= 0 or beta0 <= 0:
            raise ValueError("alpha0/beta0 must be > 0.")
        self.arms = list(arms)
        self.alpha: Dict[str, float] = {a: float(alpha0) for a in self.arms}
        self.beta: Dict[str, float] = {a: float(beta0) for a in self.arms}

    def choose_arm(self) -> str:
        best_a = self.arms[0]
        best_sample = -1.0
        for a in self.arms:
            s = random.betavariate(self.alpha[a], self.beta[a])
            if s > best_sample:
                best_sample = s
                best_a = a
        return best_a

    select = choose_arm

    def update(self, arm: str, reward01: int) -> None:
        if arm not in self.alpha:
            raise KeyError(f"Unknown arm: {arm}")
        r = 1 if int(reward01) == 1 else 0
        if r == 1:
            self.alpha[arm] += 1.0
        else:
            self.beta[arm] += 1.0