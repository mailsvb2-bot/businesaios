from __future__ import annotations

"""Staged rollout guard.

Pure function mapping metrics to rollout percentage.
"""

from dataclasses import dataclass

from config.rollout_guard_policy import RolloutGuardPolicy


@dataclass(frozen=True)
class RolloutMetrics:
    error_rate: float = 0.0


def rollout_percentage(metrics: RolloutMetrics, *, policy: RolloutGuardPolicy | None = None) -> int:
    policy = policy or RolloutGuardPolicy()
    er = float(metrics.error_rate)
    if er > policy.hard_stop_error_rate:
        return int(policy.stop_rollout_pct)
    if er > policy.staged_error_rate:
        return int(policy.staged_rollout_pct)
    return int(policy.full_rollout_pct)
