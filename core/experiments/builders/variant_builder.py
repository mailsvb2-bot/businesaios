from __future__ import annotations

from typing import Iterable, List, Tuple

from core.experiments.enums import VariantRole
from core.experiments.errors import ExperimentValidationError
from core.experiments.types import VariantSpec


class VariantBuilder:
    def build(self, definitions: Iterable[Tuple[str, VariantRole, float]]) -> List[VariantSpec]:
        variants: List[VariantSpec] = []
        total_share = 0.0
        seen_names: set[str] = set()

        for idx, (name, role, traffic_share) in enumerate(definitions, start=1):
            clean_name = name.strip()
            if not clean_name:
                raise ExperimentValidationError("variant name must be non-empty")
            if clean_name in seen_names:
                raise ExperimentValidationError(f"duplicate variant name: {clean_name}")
            if traffic_share <= 0.0:
                raise ExperimentValidationError("variant traffic_share must be > 0")

            seen_names.add(clean_name)
            total_share += traffic_share
            variants.append(
                VariantSpec(
                    variant_id=f"var_{idx}",
                    name=clean_name,
                    role=role,
                    traffic_share=traffic_share,
                )
            )

        if len(variants) != 2:
            raise ExperimentValidationError("this experiment module supports exactly two variants")
        if abs(total_share - 1.0) > 1e-9:
            raise ExperimentValidationError("variant traffic shares must sum to 1.0")

        control_count = len([item for item in variants if item.role == VariantRole.CONTROL])
        treatment_count = len([item for item in variants if item.role == VariantRole.TREATMENT])
        if control_count != 1:
            raise ExperimentValidationError("exactly one control variant is required")
        if treatment_count != 1:
            raise ExperimentValidationError("exactly one treatment variant is required")
        return variants
