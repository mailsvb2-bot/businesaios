from __future__ import annotations

from typing import Dict, Iterable, List, Tuple

from core.experiments.builders.metric_set_builder import MetricSetBuilder
from core.experiments.builders.variant_builder import VariantBuilder
from core.experiments.enums import ExperimentStatus, MetricDirection, VariantRole
from core.experiments.guards.plan_guard import ExperimentPlanGuard
from core.experiments.ids import new_experiment_id
from core.experiments.types import Experiment, ExperimentPlan


class ExperimentPlanBuilder:
    def __init__(
        self,
        variant_builder: VariantBuilder | None = None,
        metric_builder: MetricSetBuilder | None = None,
        plan_guard: ExperimentPlanGuard | None = None,
    ) -> None:
        self._variant_builder = variant_builder or VariantBuilder()
        self._metric_builder = metric_builder or MetricSetBuilder()
        self._plan_guard = plan_guard or ExperimentPlanGuard()

    def build(
        self,
        *,
        name: str,
        hypothesis: str,
        subject_key: str,
        audience_key: str,
        owner: str,
        variant_definitions: Iterable[Tuple[str, VariantRole, float]],
        metric_definitions: Iterable[Tuple[str, MetricDirection, float, bool]],
        minimum_sample_size: int,
        overlap_keys: List[str] | None = None,
        metadata: Dict[str, str] | None = None,
    ) -> ExperimentPlan:
        plan = ExperimentPlan(
            experiment_id=new_experiment_id(),
            name=name.strip(),
            hypothesis=hypothesis.strip(),
            subject_key=subject_key.strip(),
            audience_key=audience_key.strip(),
            owner=owner.strip(),
            status=ExperimentStatus.DRAFT,
            variants=self._variant_builder.build(variant_definitions),
            metrics=self._metric_builder.build(metric_definitions),
            minimum_sample_size=minimum_sample_size,
            overlap_keys=[item.strip() for item in (overlap_keys or [])],
            metadata={str(key): str(value) for key, value in dict(metadata or {}).items()},
        )
        self._plan_guard.validate(plan)
        return plan


def build_experiment(experiment_id: str, hypothesis: str, traffic_share: float) -> Experiment:
    return Experiment(
        experiment_id=experiment_id,
        hypothesis=hypothesis.strip(),
        traffic_share=float(traffic_share),
    )
