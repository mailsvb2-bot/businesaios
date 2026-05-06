from __future__ import annotations

from core.experiments.guards.experiment_overlap_guard import ExperimentOverlapGuard
from core.experiments.guards.traffic_sufficiency_guard import TrafficSufficiencyGuard
from core.experiments.guards.unsafe_rollout_guard import UnsafeRolloutGuard


class ExperimentsGuard:
    def __init__(
        self,
        overlap_guard: ExperimentOverlapGuard | None = None,
        traffic_guard: TrafficSufficiencyGuard | None = None,
        unsafe_rollout_guard: UnsafeRolloutGuard | None = None,
    ) -> None:
        self.overlap_guard = overlap_guard or ExperimentOverlapGuard()
        self.traffic_guard = traffic_guard or TrafficSufficiencyGuard()
        self.unsafe_rollout_guard = unsafe_rollout_guard or UnsafeRolloutGuard()
