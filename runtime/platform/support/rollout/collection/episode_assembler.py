from __future__ import annotations

from runtime.platform.support.contracts.episode import Episode
from runtime.platform.support.contracts.trajectory import Trajectory


class EpisodeAssembler:
    def assemble(self, trajectory: Trajectory) -> Episode:
        return Episode(trajectory=trajectory)

__all__ = [
    "EpisodeAssembler",
]
