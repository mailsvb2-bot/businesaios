from __future__ import annotations

from hashlib import sha256

from core.experiments.types import ExperimentPlan, VariantSpec


class VariantSelectionBuilder:
    def build(self, plan: ExperimentPlan, subject_id: str) -> VariantSpec:
        digest = sha256(f"{plan.experiment_id}:{subject_id}".encode("utf-8")).hexdigest()
        bucket = int(digest[:8], 16) / 0xFFFFFFFF
        cumulative = 0.0
        selected = plan.variants[-1]
        for variant in plan.variants:
            cumulative += variant.traffic_share
            if bucket <= cumulative:
                selected = variant
                break
        return selected
