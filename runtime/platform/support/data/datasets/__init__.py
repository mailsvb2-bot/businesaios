from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from runtime.platform.support.contracts.episode import Episode
from runtime.platform.support.contracts.evaluation import EvaluationResult
from runtime.platform.support.contracts.reward import Reward
from runtime.platform.support.contracts.trajectory import Trajectory
from runtime.platform.support.contracts.transition import Transition


class BenchmarkDataset:
    def __init__(self, items: Iterable[Trajectory] = ()) -> None:
        self._items = list(items)

    def items(self) -> tuple[Trajectory, ...]:
        return tuple(self._items)

class EpisodeDataset:
    def __init__(self, items: Iterable[Episode] = ()) -> None:
        self._items = list(items)

    def items(self) -> tuple[Episode, ...]:
        return tuple(self._items)

class EvaluationDataset:
    def __init__(self, items: Iterable[EvaluationResult] = ()) -> None:
        self._items = list(items)

    def items(self) -> tuple[EvaluationResult, ...]:
        return tuple(self._items)

class PreferenceDataset:
    def __init__(self) -> None:
        self._pairs: list[tuple[str, str]] = []

    def add(self, preferred: str, rejected: str) -> None:
        self._pairs.append((preferred, rejected))

    def pairs(self) -> tuple[tuple[str, str], ...]:
        return tuple(self._pairs)

class ReplayDataset:
    def __init__(self, items: Iterable[Transition] = ()) -> None:
        self._items = list(items)

    def items(self) -> tuple[Transition, ...]:
        return tuple(self._items)

class RewardDataset:
    def __init__(self, items: Iterable[Reward] = ()) -> None:
        self._items = list(items)

    def items(self) -> tuple[Reward, ...]:
        return tuple(self._items)

class ShadowTrafficDataset:
    def __init__(self) -> None:
        self._records: list[Any] = []

    def add(self, record: Any) -> None:
        self._records.append(record)

    def records(self) -> tuple[Any, ...]:
        return tuple(self._records)

class SimulationDataset:
    def __init__(self, items: Iterable[Trajectory] = ()) -> None:
        self._items = list(items)

    def items(self) -> tuple[Trajectory, ...]:
        return tuple(self._items)

class TrajectoryDataset:
    def __init__(self, items: Iterable[Trajectory] = ()) -> None:
        self._items = list(items)

    def items(self) -> tuple[Trajectory, ...]:
        return tuple(self._items)

class TransitionDataset:
    def __init__(self, items: Iterable[Transition] = ()) -> None:
        self._items = list(items)

    def items(self) -> tuple[Transition, ...]:
        return tuple(self._items)

__all__ = [
    "BenchmarkDataset",
    "EpisodeDataset",
    "EvaluationDataset",
    "PreferenceDataset",
    "ReplayDataset",
    "RewardDataset",
    "ShadowTrafficDataset",
    "SimulationDataset",
    "TrajectoryDataset",
    "TransitionDataset",
]

_MODULE_EXPORTS = {
    "benchmark_dataset": {"BenchmarkDataset": f"{__name__}:BenchmarkDataset"},
    "episode_dataset": {"EpisodeDataset": f"{__name__}:EpisodeDataset"},
    "evaluation_dataset": {"EvaluationDataset": f"{__name__}:EvaluationDataset"},
    "preference_dataset": {"PreferenceDataset": f"{__name__}:PreferenceDataset"},
    "replay_dataset": {"ReplayDataset": f"{__name__}:ReplayDataset"},
    "reward_dataset": {"RewardDataset": f"{__name__}:RewardDataset"},
    "shadow_traffic_dataset": {"ShadowTrafficDataset": f"{__name__}:ShadowTrafficDataset"},
    "simulation_dataset": {"SimulationDataset": f"{__name__}:SimulationDataset"},
    "trajectory_dataset": {"TrajectoryDataset": f"{__name__}:TrajectoryDataset"},
    "transition_dataset": {"TransitionDataset": f"{__name__}:TransitionDataset"},
}
