from __future__ import annotations

from core.experiments.errors import MetricNotDefinedError
from core.experiments.types import ExperimentPlan


class MetricMembershipGuard:
    def ensure_defined(self, plan: ExperimentPlan, primary_metric_key: str) -> None:
        metric_keys = {item.metric_key for item in plan.metrics}
        if primary_metric_key not in metric_keys:
            raise MetricNotDefinedError(
                f"metric '{primary_metric_key}' is not defined for experiment {plan.experiment_id}"
            )
