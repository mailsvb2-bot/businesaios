from __future__ import annotations

"""Monitoring metrics for rollout decisions.

These helpers are pure and deterministic (given event inputs).
"""

from dataclasses import dataclass
from typing import Dict, Iterable

from .event_store import Event


@dataclass(frozen=True)
class OnlineMetrics:
    mean_reward: float
    n: int
    mean_ltv: float


def compute_online_metrics(events: Iterable[Event], *, policy_id: str) -> OnlineMetrics:
    rewards = []
    ltvs = []
    for e in events:
        if e.event_type != "reward_observed":
            continue
        if str(e.payload.get("policy_id") or "") != str(policy_id):
            continue
        rewards.append(float(e.payload.get("reward", 0.0) or 0.0))
        ltvs.append(float(e.payload.get("ltv", 0.0) or 0.0))

    n = len(rewards)
    mean_reward = sum(rewards) / n if n else 0.0
    mean_ltv = sum(ltvs) / n if n else 0.0
    return OnlineMetrics(mean_reward=float(mean_reward), n=int(n), mean_ltv=float(mean_ltv))
