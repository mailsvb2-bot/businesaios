from __future__ import annotations


class SparseRewardSupport:
    def densify(self, reward: float, baseline: float = 0.0) -> float:
        if reward == 0.0:
            return baseline
        return reward

__all__ = [
    "SparseRewardSupport",
]
