from __future__ import annotations

"""Canonical rollout monitoring surface with compat alias submodules."""

class RolloutAnomalyDetection:
    def detect(self, metric: float, threshold: float) -> bool:
        return metric > threshold

class RolloutCost:
    def estimate(self, steps: int, price_per_step: float) -> float:
        return steps * price_per_step

class RolloutDrift:
    def drifted(self, baseline: float, current: float, threshold: float = 0.1) -> bool:
        return abs(baseline - current) > threshold

class RolloutHealth:
    def healthy(self, failed_workers: int) -> bool:
        return failed_workers == 0

class RolloutQuality:
    def score(self, average_reward: float, completion_rate: float) -> float:
        return average_reward * completion_rate

class RolloutSafety:
    def is_safe(self, flags: dict[str, bool]) -> bool:
        return not flags.get("unsafe", False)

_ALIAS_EXPORTS = {
    "rollout_anomaly_detection": "RolloutAnomalyDetection",
    "rollout_cost": "RolloutCost",
    "rollout_drift": "RolloutDrift",
    "rollout_health": "RolloutHealth",
    "rollout_quality": "RolloutQuality",
    "rollout_safety": "RolloutSafety",
}

__all__ = [
    "RolloutAnomalyDetection",
    "RolloutCost",
    "RolloutDrift",
    "RolloutHealth",
    "RolloutQuality",
    "RolloutSafety",
] + list(_ALIAS_EXPORTS)
