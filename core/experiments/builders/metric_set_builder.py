from __future__ import annotations

from typing import Iterable

from core.experiments.enums import MetricDirection
from core.experiments.errors import ExperimentValidationError
from core.experiments.types import MetricDefinition


class MetricSetBuilder:
    def build(self, definitions: Iterable[tuple[str, MetricDirection, float, bool]]) -> list[MetricDefinition]:
        metrics: list[MetricDefinition] = []
        seen: set[str] = set()

        for metric_key, direction, mde, guardrail in definitions:
            clean_key = metric_key.strip()
            if not clean_key:
                raise ExperimentValidationError("metric_key must be non-empty")
            if clean_key in seen:
                raise ExperimentValidationError(f"duplicate metric_key: {clean_key}")
            if mde < 0.0:
                raise ExperimentValidationError("minimum_detectable_effect must be >= 0")
            seen.add(clean_key)
            metrics.append(
                MetricDefinition(
                    metric_key=clean_key,
                    direction=direction,
                    minimum_detectable_effect=mde,
                    guardrail=guardrail,
                )
            )

        if not metrics:
            raise ExperimentValidationError("at least one metric is required")
        return metrics
