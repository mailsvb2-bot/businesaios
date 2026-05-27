from __future__ import annotations


class DelayedRewardCredit:
    def assign(self, rewards: list[float], gamma: float = 0.99) -> list[float]:
        output = [0.0 for _ in rewards]
        running = 0.0
        for index in reversed(range(len(rewards))):
            running = rewards[index] + gamma * running
            output[index] = running
        return output

__all__ = [
    "DelayedRewardCredit",
]
