from __future__ import annotations

from core.experiments.errors import ExperimentNotFoundError
from core.experiments.types import VariantSpec


class VariantReader:
    def __init__(self, experiment_repository) -> None:
        self._experiment_repository = experiment_repository

    def get_variant_map(self, experiment_id: str) -> dict[str, VariantSpec]:
        plan = self._experiment_repository.get(experiment_id)
        if plan is None:
            raise ExperimentNotFoundError(f"experiment not found: {experiment_id}")
        return {variant.variant_id: variant for variant in plan.variants}
