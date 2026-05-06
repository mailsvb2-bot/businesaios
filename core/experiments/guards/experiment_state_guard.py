from __future__ import annotations

from core.experiments.enums import ExperimentStatus
from core.experiments.errors import InvalidExperimentStateError
from core.experiments.types import ExperimentPlan


class ExperimentStateGuard:
    _ASSIGNABLE_STATUSES = {ExperimentStatus.ACTIVE}
    _SNAPSHOT_EVALUABLE_STATUSES = {ExperimentStatus.ACTIVE, ExperimentStatus.PAUSED}
    _REPORTABLE_STATUSES = {
        ExperimentStatus.ACTIVE,
        ExperimentStatus.PAUSED,
        ExperimentStatus.EVALUATED,
        ExperimentStatus.COMPLETED,
    }

    def ensure_assignable(self, plan: ExperimentPlan) -> None:
        if plan.status not in self._ASSIGNABLE_STATUSES:
            raise InvalidExperimentStateError(
                f"experiment is not assignable: {plan.experiment_id} status={plan.status.value}"
            )

    def ensure_snapshot_evaluable(self, plan: ExperimentPlan) -> None:
        if plan.status not in self._SNAPSHOT_EVALUABLE_STATUSES:
            raise InvalidExperimentStateError(
                f"experiment is not snapshot-evaluable: {plan.experiment_id} status={plan.status.value}"
            )

    def ensure_reportable(self, plan: ExperimentPlan) -> None:
        if plan.status not in self._REPORTABLE_STATUSES:
            raise InvalidExperimentStateError(
                f"experiment is not reportable: {plan.experiment_id} status={plan.status.value}"
            )
