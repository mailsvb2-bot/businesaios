from __future__ import annotations

import random
from typing import Any

from runtime.platform.support.contracts.trajectory import Trajectory
from runtime.platform.support.contracts.transition import Transition

class PrioritizedReplayBuffer:
    def __init__(self) -> None:
        self._items: list[tuple[float, Transition]] = []

    def add(self, priority: float, transition: Transition) -> None:
        self._items.append((priority, transition))

    def sample(self, n: int) -> list[Transition]:
        ordered = sorted(self._items, key=lambda x: -x[0])
        return [t for _, t in ordered[:n]]

class ReplayBuffer:
    def __init__(self, capacity: int = 100000) -> None:
        self.capacity = capacity
        self._items: list[Transition] = []

    def add(self, transition: Transition) -> None:
        if len(self._items) >= self.capacity:
            self._items.pop(0)
        self._items.append(transition)

    def sample(self, n: int) -> list[Transition]:
        return self._items[:n]

def fifo_eviction(items: list[Any], capacity: int) -> None:
    while len(items) > capacity:
        items.pop(0)

class ReplayIndex:
    def __init__(self) -> None:
        self._positions: dict[str, int] = {}

    def remember(self, key: str, position: int) -> None:
        self._positions[key] = position

    def lookup(self, key: str) -> int | None:
        return self._positions.get(key)

def validate_replay(items) -> bool:
    return all(item is not None for item in items)

class ReplayPersistence:
    def dump(self, transitions: list[Transition]) -> list[Transition]:
        return list(transitions)

    def load(self, payload: list[Transition]) -> list[Transition]:
        return list(payload)

def sample_replay(items, n: int):
    return list(items)[:n]

class ReservoirBuffer:
    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self._items: list[Transition] = []
        self._seen = 0

    def add(self, item: Transition) -> None:
        self._seen += 1
        if len(self._items) < self.capacity:
            self._items.append(item)
            return
        j = random.randint(0, self._seen - 1)
        if j < self.capacity:
            self._items[j] = item

class SequenceReplayBuffer:
    def __init__(self) -> None:
        self._seq: list[Trajectory] = []

    def add(self, traj: Trajectory) -> None:
        self._seq.append(traj)

    def sample(self, n: int) -> list[Trajectory]:
        return self._seq[:n]

__all__ = [
    "PrioritizedReplayBuffer",
    "ReplayBuffer",
    "ReplayIndex",
    "ReplayPersistence",
    "ReservoirBuffer",
    "SequenceReplayBuffer",
    "fifo_eviction",
    "sample_replay",
    "validate_replay",
]
