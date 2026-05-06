from __future__ import annotations

from core.experiments.errors import PreparedResultMissingError
from core.experiments.types import ExperimentResult


class ResultReader:
    def __init__(self, repository) -> None:
        self._repository = repository

    def get_latest_by_metric(self, experiment_id: str, primary_metric_key: str) -> ExperimentResult:
        result = self._repository.get_latest_by_metric(experiment_id, primary_metric_key)
        if result is None:
            raise PreparedResultMissingError("no prepared aggregate result found for experiment and metric")
        return result
