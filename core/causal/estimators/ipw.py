from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# FIX: use shared propensity utility (was duplicated in doubly_robust.py)
from core.causal.estimators._propensity import fit_stratified_propensity, stratum_key
from core.causal.estimators.base import CausalEstimator, EstimatorResult, _counts
from core.causal.math_utils import clip
from core.causal.types import CausalDataset, EffectEstimate

Json = dict[str, Any]


@dataclass(frozen=True)
class IPWEstimator(CausalEstimator):
    """Inverse propensity weighting using stratified propensity."""

    covariate_names: tuple[str, ...] = ()
    # Smoothing is useful for very sparse strata, but it introduces bias.
    # We keep it off by default and rely on clip_min/clip_max for stability.
    smoothing: float = 0.0
    clip_min: float = 0.05
    clip_max: float = 0.95
    method: str = "ipw_strata_v1"

    def estimate(self, *, dataset: CausalDataset, estimand: str = "ATE") -> EstimatorResult:
        dataset.validate()
        names = tuple(self.covariate_names)
        p = fit_stratified_propensity(dataset, names, smoothing=float(self.smoothing))

        w_t: list[float] = []
        y_t: list[float] = []
        w_c: list[float] = []
        y_c: list[float] = []

        for r in dataset.rows:
            k = stratum_key(r.covariates, names)
            ps = clip(float(p.get(k, 0.5)), float(self.clip_min), float(self.clip_max))
            t = 1.0 if float(r.treatment) >= 0.5 else 0.0
            y = float(r.outcome)
            if t >= 0.5:
                w = 1.0 / ps
                w_t.append(w)
                y_t.append(y)
            else:
                w = 1.0 / (1.0 - ps)
                w_c.append(w)
                y_c.append(y)

        def wmean(vals: list[float], weights: list[float]) -> float:
            if not vals:
                return 0.0
            s = sum(float(w) for w in weights)
            if s <= 0:
                return 0.0
            return sum(float(v) * float(w) for v, w in zip(vals, weights, strict=False)) / s

        eff = wmean(y_t, w_t) - wmean(y_c, w_c)
        n, nt, nc = _counts(dataset)
        est = EffectEstimate(
            estimand=str(estimand or "ATE"),
            effect=float(eff),
            stderr=None,
            n=n,
            n_treated=nt,
            n_control=nc,
            method=self.method,
            notes="IPW with stratified propensity (no external ML deps).",
            diagnostics={"propensity_strata": len(p)},
        )
        return EstimatorResult(estimate=est, trace={"propensity_strata": len(p)})
