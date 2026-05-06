from __future__ import annotations

from typing import Dict, Iterable, Optional

from core.experiments.errors import DuplicateAssignmentError
from core.experiments.types import ExperimentAssignment


class InMemoryAssignmentRepository:
    def __init__(self) -> None:
        self._by_experiment: Dict[str, Dict[str, ExperimentAssignment]] = {}

    def save(self, assignment: ExperimentAssignment) -> ExperimentAssignment:
        subject_map = self._by_experiment.setdefault(assignment.experiment_id, {})
        if assignment.subject_id in subject_map:
            raise DuplicateAssignmentError(
                f"assignment already exists for subject '{assignment.subject_id}'"
            )
        subject_map[assignment.subject_id] = assignment
        return assignment

    def list_by_experiment(self, experiment_id: str) -> Iterable[ExperimentAssignment]:
        return list(self._by_experiment.get(experiment_id, {}).values())

    def find_by_subject(self, experiment_id: str, subject_id: str) -> Optional[ExperimentAssignment]:
        return self._by_experiment.get(experiment_id, {}).get(subject_id)
