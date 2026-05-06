from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from core.causal.estimators.base import CausalEstimator, EstimatorResult, _counts
from core.causal.math_utils import mean
from core.causal.types import CausalDataset, EffectEstimate


Json = Dict[str, Any]


@dataclass(frozen=True)
class DiffInDiffEstimator(CausalEstimator):
    """Difference-in-Differences for panel-ish data.

    Assumes dataset rows have:
      - treatment: group indicator (treated group vs control group)
      - covariates['period']: 'pre' or 'post'

    You can build such dataset via :mod:`core.causal.builders.event_store_builder`.
    """

    period_key: str = "period"
    method: str = "diff_in_diff_v1"

    def estimate(self, *, dataset: CausalDataset, estimand: str = "ATE") -> EstimatorResult:
        dataset.validate()

        y_tp: List[float] = []  # treated, post
        y_tpre: List[float] = []
        y_cp: List[float] = []
        y_cpre: List[float] = []

        for r in dataset.rows:
            period = str((r.covariates or {}).get(self.period_key) or "")
            t = 1.0 if float(r.treatment) >= 0.5 else 0.0
            y = float(r.outcome)
            if period == "post":
                (y_tp if t >= 0.5 else y_cp).append(y)
            elif period == "pre":
                (y_tpre if t >= 0.5 else y_cpre).append(y)

        eff = (mean(y_tp) - mean(y_tpre)) - (mean(y_cp) - mean(y_cpre))
        n, nt, nc = _counts(dataset)
        est = EffectEstimate(
            estimand=str(estimand or "ATE"),
            effect=float(eff),
            stderr=None,
            n=n,
            n_treated=nt,
            n_control=nc,
            method=self.method,
            notes="Diff-in-Diff: (Tpost-Tpre) - (Cpost-Cpre).",
            diagnostics={
                "means": {
                    "treated_pre": mean(y_tpre),
                    "treated_post": mean(y_tp),
                    "control_pre": mean(y_cpre),
                    "control_post": mean(y_cp),
                }
            },
        )
        return EstimatorResult(estimate=est, trace=est.diagnostics)
