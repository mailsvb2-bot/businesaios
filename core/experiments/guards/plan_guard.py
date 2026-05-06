from __future__ import annotations

from core.experiments.enums import ExperimentStatus, VariantRole
from core.experiments.errors import ExperimentValidationError
from core.experiments.types import ExperimentPlan


class ExperimentPlanGuard:
    def validate(self, plan: ExperimentPlan) -> None:
        if not plan.name.strip():
            raise ExperimentValidationError("name must be non-empty")
        if not plan.hypothesis.strip():
            raise ExperimentValidationError("hypothesis must be non-empty")
        if not plan.subject_key.strip():
            raise ExperimentValidationError("subject_key must be non-empty")
        if not plan.audience_key.strip():
            raise ExperimentValidationError("audience_key must be non-empty")
        if not plan.owner.strip():
            raise ExperimentValidationError("owner must be non-empty")
        if plan.minimum_sample_size <= 0:
            raise ExperimentValidationError("minimum_sample_size must be > 0")
        if len(plan.variants) != 2:
            raise ExperimentValidationError("exactly two variants are required")
        if not plan.metrics:
            raise ExperimentValidationError("at least one metric is required")

        total_share = sum(item.traffic_share for item in plan.variants)
        if abs(total_share - 1.0) > 1e-9:
            raise ExperimentValidationError("variant traffic shares must sum to 1.0")

        control_count = len([item for item in plan.variants if item.role == VariantRole.CONTROL])
        treatment_count = len([item for item in plan.variants if item.role == VariantRole.TREATMENT])
        if control_count != 1:
            raise ExperimentValidationError("exactly one control variant is required")
        if treatment_count != 1:
            raise ExperimentValidationError("exactly one treatment variant is required")

        metric_keys = [item.metric_key for item in plan.metrics]
        if len(metric_keys) != len(set(metric_keys)):
            raise ExperimentValidationError("duplicate metrics are forbidden")

        for key in plan.overlap_keys:
            if not key.strip():
                raise ExperimentValidationError("overlap_keys must not contain empty values")

    def validate_for_registration(self, plan: ExperimentPlan) -> None:
        self.validate(plan)
        if plan.status != ExperimentStatus.DRAFT:
            raise ExperimentValidationError("only draft experiments may be registered")
