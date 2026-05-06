from __future__ import annotations

from core.experiments.enums import VariantRole
from core.experiments.errors import ResultConsistencyError
from core.experiments.types import ExperimentPlan, ExperimentResult


class ResultConsistencyGuard:
    def ensure_matches_plan(self, plan: ExperimentPlan, result: ExperimentResult) -> None:
        if result.experiment_id != plan.experiment_id:
            raise ResultConsistencyError("result.experiment_id does not match plan.experiment_id")

        metric_keys = {item.metric_key for item in plan.metrics}
        if result.primary_metric_key not in metric_keys:
            raise ResultConsistencyError("result.primary_metric_key is not defined in plan")

        control_variant_id = self._get_variant_id_by_role(plan, VariantRole.CONTROL)
        treatment_variant_id = self._get_variant_id_by_role(plan, VariantRole.TREATMENT)
        if result.control_variant_id != control_variant_id:
            raise ResultConsistencyError("result.control_variant_id does not match control variant")
        if result.treatment_variant_id != treatment_variant_id:
            raise ResultConsistencyError("result.treatment_variant_id does not match treatment variant")
        if result.control.variant_id != control_variant_id:
            raise ResultConsistencyError("result.control snapshot variant_id mismatch")
        if result.treatment.variant_id != treatment_variant_id:
            raise ResultConsistencyError("result.treatment snapshot variant_id mismatch")
        if result.control.exposures < 0 or result.treatment.exposures < 0:
            raise ResultConsistencyError("result exposures must be >= 0")
        if result.control.conversions < 0 or result.treatment.conversions < 0:
            raise ResultConsistencyError("result conversions must be >= 0")
        if result.control.conversions > result.control.exposures:
            raise ResultConsistencyError("control conversions must be <= control exposures")
        if result.treatment.conversions > result.treatment.exposures:
            raise ResultConsistencyError("treatment conversions must be <= treatment exposures")

    def _get_variant_id_by_role(self, plan: ExperimentPlan, role: VariantRole) -> str:
        for variant in plan.variants:
            if variant.role == role:
                return variant.variant_id
        raise ResultConsistencyError(f"variant with role '{role.value}' not found in plan")
