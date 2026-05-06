from __future__ import annotations

"""Canonical advisory scoring surface for bandit-style candidate ranking."""

import hashlib
import random
from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True)
class ArmScore:
    arm: str
    score: float
    reason: str


@dataclass(frozen=True)
class Choice:
    key: str
    reason: str


def _seeded_rng(seed: str) -> random.Random:
    s = str(seed or "")
    h = hashlib.sha256(s.encode("utf-8")).digest()
    return random.Random(int.from_bytes(h[:8], "big", signed=False))


def _ab_for_arm(*, arm: str, stats: Mapping[str, Mapping[str, float]] | None) -> tuple[float, float]:
    raw = stats.get(arm) if isinstance(stats, dict) and isinstance(stats.get(arm), dict) else {}
    try:
        a = float(raw.get("alpha", 1.0))
        b = float(raw.get("beta", 1.0))
        return max(1e-6, a), max(1e-6, b)
    except Exception:
        return 1.0, 1.0


def score_bandit_arms(
    *,
    arms: Sequence[str],
    stats: Mapping[str, Mapping[str, float]] | None,
    seed: str,
) -> tuple[ArmScore, ...]:
    if not arms:
        return ()

    rng = _seeded_rng(seed)
    scores: list[ArmScore] = []

    for arm in arms:
        a, b = _ab_for_arm(arm=str(arm), stats=stats)
        try:
            score = rng.betavariate(a, b)
        except Exception:
            score = 0.5
        scores.append(ArmScore(arm=str(arm), score=float(score), reason="thompson_score_only"))

    return tuple(scores)


def choose_bandit_arm(*, arms: Sequence[str], stats: Mapping[str, Mapping[str, float]] | None, seed: str) -> Choice:
    if not arms:
        return Choice("", "no_arms")

    scored = score_bandit_arms(arms=arms, stats=stats, seed=seed)
    if not scored:
        return Choice("", "no_arms")

    winner = max(scored, key=lambda item: item.score)
    return Choice(winner.arm, "thompson_from_score_surface")


class EpsilonGreedyBandit:
    """Deterministic epsilon-greedy bandit kept on the canonical scorer surface.

    This remains advisory-only: it scores/chooses an arm and never executes
    effects or mutates runtime state outside its internal reward table.
    """

    def __init__(self, epsilon: float = 0.1, seed: str = "bandit") -> None:
        if not (0.0 <= epsilon <= 1.0):
            raise ValueError("epsilon must be within [0.0, 1.0]")
        self.epsilon = float(epsilon)
        self._seed = str(seed or "bandit")
        self.rewards: dict[object, float] = {}
        self._t = 0

    def _u01(self, key: str) -> float:
        h = hashlib.sha256((self._seed + "|" + key).encode("utf-8")).hexdigest()
        return int(h[:8], 16) / 0xFFFFFFFF

    def choose_arm(self, arms: Sequence[object]) -> object:
        if not arms:
            raise ValueError("arms must be non-empty")
        self._t += 1
        explore = self._u01(f"explore|{self._t}") < self.epsilon
        if explore:
            idx = int(self._u01(f"choice|{self._t}") * len(arms))
            idx = min(idx, len(arms) - 1)
            return arms[idx]
        return max(arms, key=lambda arm: (self.rewards.get(arm, 0.0), str(arm)))

    select = choose_arm

    def update(self, arm: object, reward: float) -> None:
        self.rewards[arm] = self.rewards.get(arm, 0.0) + float(reward)
