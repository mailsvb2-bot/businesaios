from __future__ import annotations

from core.experiments.types import ExperimentStatusView


class ExperimentStatusProjection:
    def project(self, plan, assignments, results) -> ExperimentStatusView:
        return ExperimentStatusView(
            experiment_id=plan.experiment_id,
            status=plan.status,
            assignment_count=len(list(assignments)),
            result_count=len(list(results)),
        )
