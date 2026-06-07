from __future__ import annotations

from dataclasses import dataclass

from core.causal.estimators.base import CausalEstimator
from core.causal.estimators.diff_in_diff import DiffInDiffEstimator
from core.causal.estimators.diff_in_means import DiffInMeansEstimator
from core.causal.estimators.doubly_robust import DoublyRobustEstimator
from core.causal.estimators.ipw import IPWEstimator
from core.causal.estimators.stratified import StratifiedEstimator


@dataclass(frozen=True)
class EstimatorRegistry:
    """Small registry mapping method -> estimator."""

    estimators: dict[str, CausalEstimator]

    def get(self, method: str) -> CausalEstimator | None:
        return self.estimators.get(str(method))


def default_registry(*, covariate_names: tuple[str, ...] = ()) -> EstimatorRegistry:
    # Each estimator is small and explicit; callers can override the registry.
    covs = tuple(covariate_names)
    return EstimatorRegistry(
        estimators={
            "diff_in_means": DiffInMeansEstimator(),
            "stratified": StratifiedEstimator(covariate_names=covs),
            "ipw": IPWEstimator(covariate_names=covs),
            "dr": DoublyRobustEstimator(covariate_names=covs),
            "did": DiffInDiffEstimator(),
        }
    )
