from __future__ import annotations

from typing import Dict, Iterable, Optional

from core.experiments.types import ExperimentPlan


class InMemoryExperimentRepository:
    def __init__(self) -> None:
        self._items: dict[str, ExperimentPlan] = {}

    def save(self, plan: ExperimentPlan) -> ExperimentPlan:
        self._items[plan.experiment_id] = plan
        return plan

    def get(self, experiment_id: str) -> ExperimentPlan | None:
        return self._items.get(experiment_id)

    def list_all(self) -> Iterable[ExperimentPlan]:
        return list(self._items.values())
