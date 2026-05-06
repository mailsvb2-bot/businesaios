from __future__ import annotations

from core.experiments.ids import new_assignment_id
from core.experiments.types import ExperimentAssignment


class AssignmentWriter:
    def __init__(self, repository) -> None:
        self._repository = repository

    def save(self, *, experiment_id: str, subject_id: str, variant_id: str, assigned_at: str, correlation_id: str) -> ExperimentAssignment:
        assignment = ExperimentAssignment(
            assignment_id=new_assignment_id(),
            experiment_id=experiment_id,
            subject_id=subject_id,
            variant_id=variant_id,
            assigned_at=assigned_at,
            correlation_id=correlation_id,
        )
        return self._repository.save(assignment)
