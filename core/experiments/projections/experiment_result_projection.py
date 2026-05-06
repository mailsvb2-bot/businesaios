from __future__ import annotations

from core.experiments.types import ExperimentResultView


class ExperimentResultProjection:
    def project(self, result) -> ExperimentResultView:
        return ExperimentResultView(
            experiment_id=result.experiment_id,
            primary_metric_key=result.primary_metric_key,
            uplift=result.uplift,
            p_value=result.p_value,
            significant=result.significant,
            risk_level=result.risk_level,
            rollout_decision=result.rollout_decision,
            notes=list(result.notes),
        )
