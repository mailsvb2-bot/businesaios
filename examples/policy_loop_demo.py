# policy_loop.py
# Self-driving policy engine + reward loop + safe rollout

from __future__ import annotations

import random
import json
import pathlib
from dataclasses import dataclass
from typing import Dict, Any, List, Tuple


# ============================================================
# 1) Policy definition
# ============================================================

@dataclass
class Policy:
    """
    Deterministic policy description.

    variants:
        list of possible actions (arms of bandit)

    params:
        arbitrary config
    """
    policy_id: str
    version: str
    variants: List[str]
    params: Dict[str, Any]


# ============================================================
# 2) Simple contextual bandit (epsilon-greedy, deterministic)
# ============================================================

class BanditModel:
    """
    Minimal but production-safe bandit.

    Stores:
    - successes
    - trials
    """

    def __init__(self, variants: List[str]):
        self.trials: Dict[str, int] = {v: 0 for v in variants}
        self.rewards: Dict[str, float] = {v: 0.0 for v in variants}

    # --------------------------

    def pick_arm(self, epsilon: float = 0.05) -> str:
        """
        Exploration vs exploitation.
        """
        if random.random() < epsilon:
            return random.choice(list(self.trials.keys()))

        # best mean reward
        best_variant = None
        best_score = -1.0

        for v in self.trials:
            t = self.trials[v]
            r = self.rewards[v]
            score = r / t if t > 0 else 0.0

            if score > best_score:
                best_score = score
                best_variant = v

        return best_variant or random.choice(list(self.trials.keys()))

    # --------------------------


    select = pick_arm
    def update(self, variant: str, reward: float) -> None:
        self.trials[variant] += 1
        self.rewards[variant] += reward


# ============================================================
# 3) Policy Engine (единственная точка выбора)
# ============================================================

class PolicyEngine:
    """
    DecisionCore вызывает ТОЛЬКО это.
    """

    def __init__(self, policy: Policy, model: BanditModel):
        self.policy = policy
        self.model = model

    # --------------------------

    def choose_variant(self, context: Dict[str, Any]) -> str:
        """
        Контекст пока не используется (MVP bandit),
        но интерфейс уже правильный.
        """
        return self.model.select()


# ============================================================
# 4) Reward tracking
# ============================================================

class RewardTracker:
    """
    Честная фиксация reward.
    """

    def __init__(self):
        self._buffer: List[Tuple[str, float]] = []

    def record(self, variant: str, reward: float) -> None:
        self._buffer.append((variant, reward))

    def flush(self) -> List[Tuple[str, float]]:
        data = self._buffer[:]
        self._buffer.clear()
        return data


# ============================================================
# 5) Online learning loop
# ============================================================

class OnlineLearner:
    """
    Применяет reward к bandit-модели.
    """

    def __init__(self, model: BanditModel, tracker: RewardTracker):
        self.model = model
        self.tracker = tracker

    def step(self) -> None:
        for variant, reward in self.tracker.flush():
            self.model.update(variant, reward)


# ============================================================
# 6) Offline retrain (safe, file-based MVP)
# ============================================================

class OfflineTrainer:
    """
    Переобучение вне runtime.
    """

    def __init__(self, storage: pathlib.Path):
        self.storage = storage
        self.storage.mkdir(parents=True, exist_ok=True)

    # --------------------------

    def save_dataset(self, data: List[Tuple[str, float]]) -> pathlib.Path:
        path = self.storage / "dataset.json"
        path.write_text(json.dumps(data))
        return path

    # --------------------------

    def train(self, dataset_path: pathlib.Path, variants: List[str]) -> BanditModel:
        data = json.loads(dataset_path.read_text())

        model = BanditModel(variants)

        for variant, reward in data:
            model.update(variant, reward)

        return model


# ============================================================
# 7) Safe rollout / rollback
# ============================================================

class PolicyRegistry:
    """
    Хранит активную и предыдущую policy.
    """

    def __init__(self):
        self.active: Policy | None = None
        self.previous: Policy | None = None

    # --------------------------

    def deploy(self, policy: Policy) -> None:
        self.previous = self.active
        self.active = policy

    # --------------------------

    def rollback(self) -> None:
        if self.previous:
            self.active, self.previous = self.previous, self.active
