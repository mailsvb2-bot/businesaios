from __future__ import annotations

from dataclasses import replace

from core.experiments.enums import ExperimentStatus
from core.experiments.errors import InvalidExperimentStateError
from core.experiments.types import ExperimentPlan


class ExperimentWriter:
    def __init__(self, repository) -> None:
        self._repository = repository

    def save(self, plan: ExperimentPlan) -> ExperimentPlan:
        return self._repository.save(plan)

    def activate(self, plan: ExperimentPlan) -> ExperimentPlan:
        if plan.status != ExperimentStatus.DRAFT:
            raise InvalidExperimentStateError("only draft experiments may be activated")
        updated = replace(plan, status=ExperimentStatus.ACTIVE)
        return self._repository.save(updated)

    def mark_evaluated(self, plan: ExperimentPlan) -> ExperimentPlan:
        if plan.status not in {ExperimentStatus.ACTIVE, ExperimentStatus.PAUSED, ExperimentStatus.EVALUATED}:
            raise InvalidExperimentStateError("experiment cannot be marked evaluated from current status")
        updated = replace(plan, status=ExperimentStatus.EVALUATED)
        return self._repository.save(updated)
