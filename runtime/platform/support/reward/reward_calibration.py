from __future__ import annotations


class RewardCalibration:
    def calibrate(self, reward: float, offset: float = 0.0) -> float:
        return reward + offset

__all__ = [
    "RewardCalibration",
]
