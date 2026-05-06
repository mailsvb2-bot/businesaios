from __future__ import annotations

from core.experiments.errors import ResultValidationError


class SnapshotInputGuard:
    def validate(
        self,
        *,
        primary_metric_key: str,
        control_exposures: int,
        control_conversions: int,
        treatment_exposures: int,
        treatment_conversions: int,
        control_value: float,
        treatment_value: float,
    ) -> None:
        if not primary_metric_key.strip():
            raise ResultValidationError("primary_metric_key must be non-empty")
        if control_exposures < 0:
            raise ResultValidationError("control_exposures must be >= 0")
        if treatment_exposures < 0:
            raise ResultValidationError("treatment_exposures must be >= 0")
        if control_conversions < 0:
            raise ResultValidationError("control_conversions must be >= 0")
        if treatment_conversions < 0:
            raise ResultValidationError("treatment_conversions must be >= 0")
        if control_conversions > control_exposures:
            raise ResultValidationError("control_conversions must be <= control_exposures")
        if treatment_conversions > treatment_exposures:
            raise ResultValidationError("treatment_conversions must be <= treatment_exposures")
        if control_value < 0.0:
            raise ResultValidationError("control_value must be >= 0")
        if treatment_value < 0.0:
            raise ResultValidationError("treatment_value must be >= 0")
