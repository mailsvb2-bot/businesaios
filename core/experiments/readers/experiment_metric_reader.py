from __future__ import annotations

from typing import Dict

from core.experiments.errors import ExperimentNotFoundError
from core.experiments.types import MetricDefinition


class ExperimentMetricReader:
    def __init__(self, experiment_repository) -> None:
        self._experiment_repository = experiment_repository

    def get_metric_map(self, experiment_id: str) -> Dict[str, MetricDefinition]:
        plan = self._experiment_repository.get(experiment_id)
        if plan is None:
            raise ExperimentNotFoundError(f"experiment not found: {experiment_id}")
        return {metric.metric_key: metric for metric in plan.metrics}
