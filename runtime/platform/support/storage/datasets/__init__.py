from __future__ import annotations

"""Canonical owner for generated dataset store compatibility surfaces."""

from runtime.platform.support.storage.generated_stores import (
    BenchmarkStore,
    DatasetStore,
    PreferenceStore,
    ReplayStore,
    RolloutStore,
    SimulationStore,
)

_ALIAS_EXPORTS = {
    "benchmark_store": "BenchmarkStore",
    "dataset_store": "DatasetStore",
    "preference_store": "PreferenceStore",
    "replay_store": "ReplayStore",
    "rollout_store": "RolloutStore",
    "simulation_store": "SimulationStore",
}

__all__ = [
    "DatasetStore",
    "BenchmarkStore",
    "PreferenceStore",
    "ReplayStore",
    "RolloutStore",
    "SimulationStore",
]
