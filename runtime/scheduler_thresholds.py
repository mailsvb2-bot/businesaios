from __future__ import annotations


def compute_thresholds(*, base_reward: float, base_ltv: float, rollback_drop: float) -> tuple[float, float]:
    reward_threshold = float(base_reward) * (1.0 - float(rollback_drop))
    ltv_threshold = float(base_ltv) * (1.0 - float(rollback_drop))
    return reward_threshold, ltv_threshold
