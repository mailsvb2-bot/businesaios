from __future__ import annotations

from typing import Iterable, Optional, Protocol

from core.experiments.types import (
    EvaluationSummary,
    Experiment,
    ExperimentAssignment,
    ExperimentPlan,
    ExperimentResult,
)


class ExperimentRepositoryContract(Protocol):
    def save(self, plan: ExperimentPlan) -> ExperimentPlan: ...
    def get(self, experiment_id: str) -> Optional[ExperimentPlan]: ...
    def list_all(self) -> Iterable[ExperimentPlan]: ...


class AssignmentRepositoryContract(Protocol):
    def save(self, assignment: ExperimentAssignment) -> ExperimentAssignment: ...
    def list_by_experiment(self, experiment_id: str) -> Iterable[ExperimentAssignment]: ...
    def find_by_subject(self, experiment_id: str, subject_id: str) -> Optional[ExperimentAssignment]: ...


class ResultRepositoryContract(Protocol):
    def save(self, result: ExperimentResult) -> ExperimentResult: ...
    def get_latest(self, experiment_id: str) -> Optional[ExperimentResult]: ...
    def get_latest_by_metric(self, experiment_id: str, primary_metric_key: str) -> Optional[ExperimentResult]: ...
    def list_by_experiment(self, experiment_id: str) -> Iterable[ExperimentResult]: ...


class ExperimentsServiceContract(Protocol):
    def register_experiment(self, plan: ExperimentPlan) -> ExperimentPlan: ...
    def assign_subject(
        self,
        experiment_id: str,
        subject_id: str,
        correlation_id: str,
        assigned_at: str,
    ) -> ExperimentAssignment: ...
    def evaluate(self, experiment_id: str, primary_metric_key: str) -> EvaluationSummary: ...


__all__ = [
    "Experiment",
    "ExperimentAssignment",
    "ExperimentPlan",
    "ExperimentResult",
    "EvaluationSummary",
    "ExperimentRepositoryContract",
    "AssignmentRepositoryContract",
    "ResultRepositoryContract",
    "ExperimentsServiceContract",
]
