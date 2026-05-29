from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.causal.estimators.base import CausalEstimator, EstimatorResult, _counts
from core.causal.math_utils import mean, stderr_of_mean
from core.causal.types import CausalDataset, EffectEstimate

Json = dict[str, Any]


@dataclass(frozen=True)
class DiffInMeansEstimator(CausalEstimator):
    """ATE by naive difference in means: E[Y|T=1] - E[Y|T=0]."""

    method: str = "diff_in_means_v1"

    def estimate(self, *, dataset: CausalDataset, estimand: str = "ATE") -> EstimatorResult:
        dataset.validate()
        treated: list[float] = []
        control: list[float] = []
        for r in dataset.rows:
            (treated if float(r.treatment) >= 0.5 else control).append(float(r.outcome))

        eff = mean(treated) - mean(control)
        # crude stderr assuming independent groups
        se = (stderr_of_mean(treated) ** 2 + stderr_of_mean(control) ** 2) ** 0.5
        n, nt, nc = _counts(dataset)
        est = EffectEstimate(
            estimand=str(estimand or "ATE"),
            effect=float(eff),
            stderr=float(se),
            n=n,
            n_treated=nt,
            n_control=nc,
            method=self.method,
            notes="Unadjusted difference in means (observational -> biased if confounded).",
        )
        return EstimatorResult(estimate=est, trace={"treated_mean": mean(treated), "control_mean": mean(control)})
