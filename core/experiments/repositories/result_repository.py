from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from core.experiments.types import ExperimentResult


class InMemoryResultRepository:
    def __init__(self) -> None:
        self._by_experiment: dict[str, list[ExperimentResult]] = {}

    def save(self, result: ExperimentResult) -> ExperimentResult:
        self._by_experiment.setdefault(result.experiment_id, []).append(result)
        return result

    def get_latest(self, experiment_id: str) -> ExperimentResult | None:
        items = self._by_experiment.get(experiment_id, [])
        return items[-1] if items else None

    def get_latest_by_metric(self, experiment_id: str, primary_metric_key: str) -> ExperimentResult | None:
        items = self._by_experiment.get(experiment_id, [])
        for item in reversed(items):
            if item.primary_metric_key == primary_metric_key:
                return item
        return None

    def list_by_experiment(self, experiment_id: str) -> Iterable[ExperimentResult]:
        return list(self._by_experiment.get(experiment_id, []))
