from __future__ import annotations

from runtime.platform.support.contracts.trajectory import Trajectory
from runtime.platform.support.contracts.episode import Episode
from runtime.platform.support.contracts.rollout import RolloutResult
from runtime.platform.support.canon.ids import new_rollout_id


class Collector:
    def build_rollout(self, trajectories: list[Trajectory]) -> RolloutResult:
        episodes = [Episode(trajectory=trajectory) for trajectory in trajectories]
        return RolloutResult(rollout_id=new_rollout_id(), episodes=episodes)

__all__ = [
    "Collector",
]
