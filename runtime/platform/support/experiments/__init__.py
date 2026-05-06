from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping

class ABTesting:
    def split(self, population: list[object]) -> tuple[list[object], list[object]]:
        midpoint = len(population) // 2
        return population[:midpoint], population[midpoint:]

class CanaryRegistry:
    def __init__(self) -> None:
        self._items: dict[str, dict] = {}

    def register(self, candidate_id: str, payload: dict) -> None:
        self._items[candidate_id] = dict(payload)

@dataclass(frozen=True)
class ExperimentIdentity:
    experiment_id: str

class ExperimentLineage:
    def __init__(self) -> None:
        self._parents: dict[str, str] = {}

    def record(self, child_experiment: str, parent_experiment: str) -> None:
        self._parents[child_experiment] = parent_experiment

@dataclass(frozen=True)
class ExperimentMetadata:
    name: str
    labels: Mapping[str, Any]

class ExperimentRegistry:
    def __init__(self) -> None:
        self._items: Dict[str, dict] = {}

    def register(self, experiment_id: str, payload: dict) -> None:
        self._items[experiment_id] = dict(payload)

    def get(self, experiment_id: str) -> dict:
        return dict(self._items[experiment_id])

class ExperimentSearch:
    def find(self, experiments: list[dict], tag: str) -> list[dict]:
        return [experiment for experiment in experiments if tag in experiment.get("tags", [])]

class ExperimentTags:
    def apply(self, payload: dict, tags: list[str]) -> dict:
        updated = dict(payload)
        updated["tags"] = list(tags)
        return updated

class ExperimentTracker:
    def __init__(self) -> None:
        self._events: list[dict] = []

    def track(self, event: dict) -> None:
        self._events.append(dict(event))

    def events(self) -> list[dict]:
        return list(self._events)

class ShadowRegistry:
    def __init__(self) -> None:
        self._items: dict[str, dict] = {}

    def register(self, candidate_id: str, payload: dict) -> None:
        self._items[candidate_id] = dict(payload)

class TrialAllocator:
    def allocate(self, candidates: list[str], slots: int) -> list[str]:
        return list(candidates[:slots])

class TrialRegistry:
    def __init__(self) -> None:
        self._trials: Dict[str, dict] = {}

    def register(self, trial_id: str, payload: dict) -> None:
        self._trials[trial_id] = dict(payload)

    def get(self, trial_id: str) -> dict:
        return dict(self._trials[trial_id])

class TrialScheduler:
    def schedule(self, trials):
        return list(trials)

_EXPERIMENT_COMPAT_EXPORTS = {
    "ab_testing": {"ABTesting": f"{__name__}:ABTesting"},
    "canary_registry": {"CanaryRegistry": f"{__name__}:CanaryRegistry"},
    "experiment_identity": {"ExperimentIdentity": f"{__name__}:ExperimentIdentity"},
    "experiment_lineage": {"ExperimentLineage": f"{__name__}:ExperimentLineage"},
    "experiment_metadata": {"ExperimentMetadata": f"{__name__}:ExperimentMetadata"},
    "experiment_registry": {"ExperimentRegistry": f"{__name__}:ExperimentRegistry"},
    "experiment_search": {"ExperimentSearch": f"{__name__}:ExperimentSearch"},
    "experiment_tags": {"ExperimentTags": f"{__name__}:ExperimentTags"},
    "experiment_tracker": {"ExperimentTracker": f"{__name__}:ExperimentTracker"},
    "shadow_registry": {"ShadowRegistry": f"{__name__}:ShadowRegistry"},
    "trial_allocator": {"TrialAllocator": f"{__name__}:TrialAllocator"},
    "trial_registry": {"TrialRegistry": f"{__name__}:TrialRegistry"},
    "trial_scheduler": {"TrialScheduler": f"{__name__}:TrialScheduler"},
}

__all__ = [
    "ABTesting",
    "CanaryRegistry",
    "ExperimentIdentity",
    "ExperimentLineage",
    "ExperimentMetadata",
    "ExperimentRegistry",
    "ExperimentSearch",
    "ExperimentTags",
    "ExperimentTracker",
    "ShadowRegistry",
    "TrialAllocator",
    "TrialRegistry",
    "TrialScheduler",
]
