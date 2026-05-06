from __future__ import annotations

from core.experiments.errors import ExperimentNotFoundError
from core.experiments.types import ExperimentPlan


class ExperimentReader:
    def __init__(self, repository) -> None:
        self._repository = repository

    def get(self, experiment_id: str) -> ExperimentPlan:
        plan = self._repository.get(experiment_id)
        if plan is None:
            raise ExperimentNotFoundError(f"experiment not found: {experiment_id}")
        return plan
