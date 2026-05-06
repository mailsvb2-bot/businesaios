from __future__ import annotations


class ExperimentsError(Exception):
    pass


class ExperimentValidationError(ExperimentsError):
    pass


class ExperimentNotFoundError(ExperimentsError):
    pass


class InvalidExperimentStateError(ExperimentsError):
    pass


class AssignmentValidationError(ExperimentsError):
    pass


class DuplicateAssignmentError(AssignmentValidationError):
    pass


class MetricNotDefinedError(ExperimentsError):
    pass


class ResultValidationError(ExperimentsError):
    pass


class PreparedResultMissingError(ResultValidationError):
    pass


class ResultConsistencyError(ResultValidationError):
    pass


class ExperimentGuardViolation(ExperimentsError):
    pass


class ExperimentOverlapViolation(ExperimentGuardViolation):
    pass


class TrafficSufficiencyViolation(ExperimentGuardViolation):
    pass


class UnsafeRolloutViolation(ExperimentGuardViolation):
    pass
