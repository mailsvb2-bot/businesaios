from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from core.causal.estimators.base import CausalEstimator, EstimatorResult, _counts
from core.causal.math_utils import mean
from core.causal.types import CausalDataset, EffectEstimate

Json = dict[str, Any]


def _stratum_key(cov: Mapping[str, Any], names: Sequence[str]) -> str:
    parts: list[str] = []
    for n in names:
        v = cov.get(n)
        if v is None:
            parts.append(f"{n}=__NA__")
        else:
            parts.append(f"{n}={str(v)}")
    return "|".join(parts)


@dataclass(frozen=True)
class StratifiedEstimator(CausalEstimator):
    """Backdoor-like adjustment by exact stratification on selected covariates."""

    covariate_names: tuple[str, ...] = ()
    min_group: int = 3
    method: str = "stratified_v1"

    def estimate(self, *, dataset: CausalDataset, estimand: str = "ATE") -> EstimatorResult:
        dataset.validate()
        names = tuple(self.covariate_names)
        groups: dict[str, list[tuple[float, float]]] = {}
        for r in dataset.rows:
            k = _stratum_key(r.covariates, names)
            groups.setdefault(k, []).append((float(r.treatment), float(r.outcome)))

        # Weighted by stratum size.
        total_n = 0
        eff_sum = 0.0
        used = 0
        dropped = 0
        for k, items in groups.items():
            treated = [y for t, y in items if t >= 0.5]
            control = [y for t, y in items if t < 0.5]
            if len(treated) < int(self.min_group) or len(control) < int(self.min_group):
                dropped += 1
                continue
            n_k = len(items)
            total_n += n_k
            eff_sum += float(n_k) * (mean(treated) - mean(control))
            used += 1

        eff = eff_sum / float(total_n) if total_n else 0.0
        n, nt, nc = _counts(dataset)
        est = EffectEstimate(
            estimand=str(estimand or "ATE"),
            effect=float(eff),
            stderr=None,
            n=n,
            n_treated=nt,
            n_control=nc,
            method=self.method,
            notes="Exact stratification on selected covariates (drops sparse strata).",
            diagnostics={"strata_total": len(groups), "strata_used": used, "strata_dropped": dropped},
        )
        return EstimatorResult(estimate=est, trace={"groups": len(groups), "used": used, "dropped": dropped})
