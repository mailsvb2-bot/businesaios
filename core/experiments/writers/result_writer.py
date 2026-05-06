from __future__ import annotations

from core.experiments.enums import RiskLevel, RolloutDecision
from core.experiments.ids import new_result_id
from core.experiments.types import ExperimentResult, VariantMetricSnapshot


class ResultWriter:
    def __init__(self, repository) -> None:
        self._repository = repository

    def save(
        self,
        *,
        experiment_id: str,
        primary_metric_key: str,
        control_variant_id: str,
        treatment_variant_id: str,
        control: VariantMetricSnapshot,
        treatment: VariantMetricSnapshot,
        uplift: float,
        p_value: float,
        significant: bool,
        risk_level: RiskLevel,
        rollout_decision: RolloutDecision,
        notes: list[str] | None = None,
    ) -> ExperimentResult:
        result = ExperimentResult(
            result_id=new_result_id(),
            experiment_id=experiment_id,
            primary_metric_key=primary_metric_key,
            control_variant_id=control_variant_id,
            treatment_variant_id=treatment_variant_id,
            control=control,
            treatment=treatment,
            uplift=uplift,
            p_value=p_value,
            significant=significant,
            risk_level=risk_level,
            rollout_decision=rollout_decision,
            notes=list(notes or []),
        )
        return self._repository.save(result)
