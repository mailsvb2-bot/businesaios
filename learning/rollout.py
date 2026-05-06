from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class RolloutState:
    active_policy_id: str
    candidate_policy_id: Optional[str]
    rollout_pct: int
    status: str


class RolloutManager:
    def __init__(self, initial_policy_id: str) -> None:
        self._state = RolloutState(active_policy_id=str(initial_policy_id), candidate_policy_id=None, rollout_pct=0, status="stable")
        self._baseline_metrics: Dict[str, float] = {
            "offline_mean_reward": 0.0,
            "online_mean_reward": 0.0,
            "online_mean_ltv": 0.0,
            "online_n": 0.0,
        }

    def baseline_metrics(self) -> Dict[str, float]:
        return dict(self._baseline_metrics)

    def set_baseline_metrics(self, metrics: Dict[str, float]) -> None:
        self._baseline_metrics = dict(metrics)

    def begin_rollout(self, candidate_policy_id: str, pct: int) -> RolloutState:
        self._state = RolloutState(active_policy_id=self._state.active_policy_id, candidate_policy_id=str(candidate_policy_id), rollout_pct=int(pct), status="rolling")
        return self._state

    def commit(self, new_baseline_metrics: Dict[str, float]) -> RolloutState:
        assert self._state.candidate_policy_id is not None
        self._state = RolloutState(active_policy_id=self._state.candidate_policy_id, candidate_policy_id=None, rollout_pct=0, status="stable")
        self._baseline_metrics = dict(new_baseline_metrics)
        return self._state

    def rollback(self) -> RolloutState:
        self._state = RolloutState(active_policy_id=self._state.active_policy_id, candidate_policy_id=None, rollout_pct=0, status="rollback")
        return self._state

    def state(self) -> RolloutState:
        return self._state


class RolloutGuardViolation(Exception):
    """Raised when rollout lifecycle rules are violated."""


@dataclass(frozen=True)
class PolicyRollout:
    rollout_id: str
    baseline_policy_id: str
    candidate_policy_id: str
    traffic_fraction: float
    started_at_ms: int

    @property
    def policy_id(self) -> str:
        return self.candidate_policy_id


class PolicyRolloutManager:
    """Controls safe rollout lifecycle."""

    def __init__(self, soak_period_ms: int = 6 * 60 * 60 * 1000) -> None:
        self._soak_period_ms = int(soak_period_ms)
        self._rollouts: Dict[str, PolicyRollout] = {}

    def start_rollout(
        self,
        rollout_id: str,
        baseline_policy_id: Optional[str] = None,
        candidate_policy_id: Optional[str] = None,
        traffic_fraction: float = 0.0,
        now_ms: Optional[int] = None,
        **legacy_kwargs,
    ) -> PolicyRollout:
        if baseline_policy_id is None:
            baseline_policy_id = legacy_kwargs.pop("baseline_policy", None)
        if candidate_policy_id is None:
            candidate_policy_id = legacy_kwargs.pop("candidate_policy", None)
        if legacy_kwargs:
            unexpected = ", ".join(sorted(legacy_kwargs))
            raise TypeError(f"Unexpected keyword arguments: {unexpected}")
        if not rollout_id:
            raise RolloutGuardViolation("rollout_id is required.")
        if not baseline_policy_id or not candidate_policy_id:
            raise RolloutGuardViolation("Both baseline_policy_id and candidate_policy_id are required.")
        if baseline_policy_id == candidate_policy_id:
            raise RolloutGuardViolation("Baseline and candidate policies must differ.")
        if not (0.0 < traffic_fraction <= 1.0):
            raise RolloutGuardViolation("traffic_fraction must be in (0, 1].")
        if rollout_id in self._rollouts:
            raise RolloutGuardViolation(f"Rollout '{rollout_id}' already exists.")
        started_at_ms = now_ms if now_ms is not None else int(time.time() * 1000)
        rollout = PolicyRollout(
            rollout_id=str(rollout_id),
            baseline_policy_id=str(baseline_policy_id),
            candidate_policy_id=str(candidate_policy_id),
            traffic_fraction=float(traffic_fraction),
            started_at_ms=int(started_at_ms),
        )
        self._rollouts[rollout_id] = rollout
        return rollout

    @property
    def rollouts(self) -> Dict[str, PolicyRollout]:
        return self._rollouts

    def get_rollout(self, rollout_id: str) -> PolicyRollout:
        try:
            return self._rollouts[rollout_id]
        except KeyError as exc:
            raise RolloutGuardViolation(f"Unknown rollout '{rollout_id}'.") from exc

    def can_promote(self, rollout_id: str, now_ms: Optional[int] = None) -> bool:
        rollout = self.get_rollout(rollout_id)
        current_ms = now_ms if now_ms is not None else int(time.time() * 1000)
        return (current_ms - rollout.started_at_ms) >= self._soak_period_ms

    def promote(self, rollout_id: str, now_ms: Optional[int] = None) -> str:
        if not self.can_promote(rollout_id, now_ms=now_ms):
            raise RolloutGuardViolation("Rollout soak period has not completed yet.")
        rollout = self.get_rollout(rollout_id)
        return rollout.candidate_policy_id

    def delete_rollout(self, rollout_id: str) -> None:
        self.get_rollout(rollout_id)
        del self._rollouts[rollout_id]


@dataclass(frozen=True)
class RolloutDecision:
    allow: bool
    reason: str = ""


class RolloutGuard:
    """Pure rollout guard used by decision-adjacent services to prevent unsafe policy rollout."""

    def allow_rollout(self, *, policy_id: str, canary: bool, recent_reward: float | None = None) -> RolloutDecision:
        del policy_id
        if canary and (recent_reward is not None and float(recent_reward) < 0.0):
            return RolloutDecision(False, "negative_reward")
        return RolloutDecision(True, "")
