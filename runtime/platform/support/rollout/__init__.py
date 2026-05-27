from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Protocol

from runtime.platform.support.contracts.rollout import RolloutResult


class RolloutCollector(Protocol):
    def collect(self) -> RolloutResult:
        ...

@dataclass(frozen=True)
class RolloutBudget:
    max_steps: int

@dataclass(frozen=True)
class RolloutIdentity:
    rollout_id: str

@dataclass(frozen=True)
class RolloutLimits:
    max_parallel_workers: int

class RolloutLineage:
    def __init__(self) -> None:
        self._parents: Dict[str, str] = {}

    def record(self, rollout_id: str, parent_rollout_id: str) -> None:
        self._parents[rollout_id] = parent_rollout_id

    def parent_of(self, rollout_id: str) -> str | None:
        return self._parents.get(rollout_id)

@dataclass(frozen=True)
class RolloutMetrics:
    episodes: int
    transitions: int
    reward_total: float

class RolloutRegistry:
    def __init__(self) -> None:
        self._items: Dict[str, dict] = {}

    def register(self, rollout_id: str, payload: dict) -> None:
        self._items[rollout_id] = dict(payload)

    def get(self, rollout_id: str) -> dict | None:
        item = self._items.get(rollout_id)
        return None if item is None else dict(item)

@dataclass(frozen=True)
class RolloutRequest:
    environment_name: str
    policy_name: str
    max_episodes: int

@dataclass(frozen=True)
class StoredRolloutResult:
    rollout_id: str
    result: RolloutResult

@dataclass(frozen=True)
class RolloutSpec:
    max_episodes: int
    max_steps_per_episode: int

__all__ = [
    "RolloutBudget",
    "RolloutCollector",
    "RolloutIdentity",
    "RolloutLimits",
    "RolloutLineage",
    "RolloutMetrics",
    "RolloutRegistry",
    "RolloutRequest",
    "RolloutSpec",
    "StoredRolloutResult",
]

_MODULE_EXPORTS = {
    "contracts": {"RolloutCollector": f"{__name__}:RolloutCollector"},
    "rollout_budget": {"RolloutBudget": f"{__name__}:RolloutBudget"},
    "rollout_identity": {"RolloutIdentity": f"{__name__}:RolloutIdentity"},
    "rollout_limits": {"RolloutLimits": f"{__name__}:RolloutLimits"},
    "rollout_lineage": {"RolloutLineage": f"{__name__}:RolloutLineage"},
    "rollout_metrics": {"RolloutMetrics": f"{__name__}:RolloutMetrics"},
    "rollout_registry": {"RolloutRegistry": f"{__name__}:RolloutRegistry"},
    "rollout_request": {"RolloutRequest": f"{__name__}:RolloutRequest"},
    "rollout_result": {"StoredRolloutResult": f"{__name__}:StoredRolloutResult"},
    "rollout_spec": {"RolloutSpec": f"{__name__}:RolloutSpec"},
}
