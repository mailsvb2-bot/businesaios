from __future__ import annotations

from dataclasses import dataclass
from typing import List

from core.math import ThompsonBernoulli


@dataclass
class CreativeArm:
    creative_id: str
    offer_arm: str


@dataclass(frozen=True)
class CreativeArmScore:
    creative_id: str
    score: float
    reason: str


class CreativeThompsonBandit:
    """
    Thompson sampling over creative variants.

    Canonical safe surface:
    - score_all() for advisory ranking
    - select() kept only as legacy compatibility wrapper
    """

    def __init__(self, arms: List[CreativeArm]):
        if not arms:
            raise ValueError("arms must be non-empty.")
        self.arms = list(arms)
        self._ts = ThompsonBernoulli([a.creative_id for a in self.arms])

    def score_all(self) -> list[CreativeArmScore]:
        scored: list[CreativeArmScore] = []
        for arm in self.arms:
            alpha = float(self._ts.alpha[str(arm.creative_id)])
            beta = float(self._ts.beta[str(arm.creative_id)])
            denom = float(alpha + beta) if (alpha + beta) else 1.0
            expected = float(alpha) / denom
            scored.append(
                CreativeArmScore(
                    creative_id=str(arm.creative_id),
                    score=expected,
                    reason="posterior_mean_score_only",
                )
            )
        return scored

    def choose_arm(self) -> str:
        return self._ts.select()


    select = choose_arm
    def update(self, creative_id: str, reward01: int) -> None:
        self._ts.update(creative_id, reward01)