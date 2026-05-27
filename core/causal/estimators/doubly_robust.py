from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from config.final_hidden_logic_policy import DEFAULT_DOUBLY_ROBUST_POLICY

# FIX: use shared propensity utility (was duplicated from ipw.py)
from core.causal.estimators._propensity import fit_stratified_propensity, stratum_key
from core.causal.estimators.base import CausalEstimator, EstimatorResult, _counts
from core.causal.feature_encoding import FeatureEncoder
from core.causal.math_utils import clip, dot, linear_regression_fit
from core.causal.types import CausalDataset, EffectEstimate

Json = Dict[str, Any]


@dataclass(frozen=True)
class DoublyRobustEstimator(CausalEstimator):
    """Doubly-robust ATE with:

    - Propensity: stratified frequency model
    - Outcome regression: OLS on encoded covariates

    If either model is approximately correct, estimate is more robust.
    """

    covariate_names: Tuple[str, ...] = ()
    # Smoothing is useful for very sparse strata, but it introduces bias.
    # We keep it off by default and rely on clip_min/clip_max for stability.
    smoothing: float = DEFAULT_DOUBLY_ROBUST_POLICY.default_smoothing
    clip_min: float = DEFAULT_DOUBLY_ROBUST_POLICY.default_clip_min
    clip_max: float = DEFAULT_DOUBLY_ROBUST_POLICY.default_clip_max
    categorical_limit: int = DEFAULT_DOUBLY_ROBUST_POLICY.default_categorical_limit
    method: str = DEFAULT_DOUBLY_ROBUST_POLICY.default_method

    def estimate(self, *, dataset: CausalDataset, estimand: str = "ATE") -> EstimatorResult:
        dataset.validate()
        names = tuple(self.covariate_names)

        # Propensity by strata (shared utility)
        p = fit_stratified_propensity(dataset, names, smoothing=float(self.smoothing))

        # Outcome regression on covariates (separately for treated/control)
        covs = [dict(r.covariates) for r in dataset.rows]
        enc = FeatureEncoder(covariate_names=list(names), categorical_limit=int(self.categorical_limit))
        enc.observe(covs)
        X = enc.transform(covs).x

        y = [float(r.outcome) for r in dataset.rows]
        t = [DEFAULT_DOUBLY_ROBUST_POLICY.treated_value if float(r.treatment) >= DEFAULT_DOUBLY_ROBUST_POLICY.treatment_threshold else DEFAULT_DOUBLY_ROBUST_POLICY.control_value for r in dataset.rows]

        # Fit two OLS models: mu1(x), mu0(x)
        X1 = [xi for xi, ti in zip(X, t) if ti >= DEFAULT_DOUBLY_ROBUST_POLICY.treatment_threshold]
        y1 = [yi for yi, ti in zip(y, t) if ti >= DEFAULT_DOUBLY_ROBUST_POLICY.treatment_threshold]
        X0 = [xi for xi, ti in zip(X, t) if ti < DEFAULT_DOUBLY_ROBUST_POLICY.treatment_threshold]
        y0 = [yi for yi, ti in zip(y, t) if ti < DEFAULT_DOUBLY_ROBUST_POLICY.treatment_threshold]

        b1 = linear_regression_fit(X1, y1).coef if X1 else [DEFAULT_DOUBLY_ROBUST_POLICY.control_value for _ in range(len(X[0]))]
        b0 = linear_regression_fit(X0, y0).coef if X0 else [DEFAULT_DOUBLY_ROBUST_POLICY.control_value for _ in range(len(X[0]))]

        # DR score per unit
        scores: List[float] = []
        for r, xi, yi, ti in zip(dataset.rows, X, y, t):
            k = stratum_key(r.covariates, names)
            ps = clip(float(p.get(k, DEFAULT_DOUBLY_ROBUST_POLICY.propensity_fallback)), float(self.clip_min), float(self.clip_max))
            mu1 = dot(b1, xi)
            mu0 = dot(b0, xi)
            # AIPW
            s = (mu1 - mu0) + (ti * (yi - mu1) / ps) - ((DEFAULT_DOUBLY_ROBUST_POLICY.treated_value - ti) * (yi - mu0) / (DEFAULT_DOUBLY_ROBUST_POLICY.treated_value - ps))
            scores.append(float(s))

        eff = sum(scores) / float(len(scores)) if scores else DEFAULT_DOUBLY_ROBUST_POLICY.control_value
        n, nt, nc = _counts(dataset)
        est = EffectEstimate(
            estimand=str(estimand or "ATE"),
            effect=float(eff),
            stderr=None,
            n=n,
            n_treated=nt,
            n_control=nc,
            method=self.method,
            notes=DEFAULT_DOUBLY_ROBUST_POLICY.default_notes,
            diagnostics={"propensity_strata": len(p), "features": len(X[0]) if X else DEFAULT_DOUBLY_ROBUST_POLICY.zero_features},
        )
        return EstimatorResult(estimate=est, trace={"propensity_strata": len(p), "features": len(X[0]) if X else DEFAULT_DOUBLY_ROBUST_POLICY.zero_features})
