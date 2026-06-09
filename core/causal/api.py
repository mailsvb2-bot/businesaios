from __future__ import annotations

from dataclasses import asdict
from typing import Any

from core.causal.bootstrap import bootstrap_ci
from core.causal.registry import EstimatorRegistry, default_registry
from core.causal.types import CausalDataset, CausalQuery, CausalResult, EffectEstimate

Json = dict[str, Any]


def _pick_method(query: CausalQuery, dataset: CausalDataset) -> str:
    m = str(query.method or "").strip().lower()
    if m and m != "auto":
        return m

    # Heuristic: if dataset has 'period' covariate -> DiD can be meaningful.
    has_period = any(str((r.covariates or {}).get("period") or "") in {"pre", "post"} for r in dataset.rows)
    if has_period:
        return "did"

    # If covariates provided, prefer DR.
    if query.covariate_names:
        return "dr"

    return "diff_in_means"


def estimate_causal_effect(
    dataset: CausalDataset,
    *,
    query: CausalQuery,
    registry: EstimatorRegistry | None = None,
    bootstrap: bool = True,
    bootstrap_n: int = 400,
    bootstrap_seed: int = 0,
) -> CausalResult:
    """Estimate a causal effect from a validated dataset.

    This function is intentionally pure (no event store reads).
    """

    dataset.validate()
    reg = registry or default_registry(covariate_names=tuple(query.covariate_names))
    method = _pick_method(query, dataset)
    est = reg.get(method)
    if est is None:
        raise ValueError(f"Unknown causal method: {method}")

    res = est.estimate(dataset=dataset, estimand=query.estimand)
    e = res.estimate

    # Add bootstrap uncertainty if estimator didn't provide it.
    if bootstrap and e.stderr is None:
        # bootstrap the estimator effect (not the mean) with fixed seed.
        import random

        rnd = random.Random(int(bootstrap_seed))
        effects = []
        rows = list(dataset.rows)
        n = len(rows)
        for _ in range(int(bootstrap_n)):
            sample = [rows[rnd.randrange(0, n)] for _ in range(n)]
            bs_res = est.estimate(dataset=CausalDataset(rows=sample), estimand=query.estimand)
            effects.append(float(bs_res.estimate.effect))
        bs = bootstrap_ci(effects, n_boot=max(200, int(bootstrap_n) // 2), seed=int(bootstrap_seed) +11)
        e = EffectEstimate(
            **{
                **asdict(e),
                "stderr": float(bs.stderr),
                "ci95_low": float(bs.ci95_low),
                "ci95_high": float(bs.ci95_high),
            }
        )

    trace: Json = {"method": method, "bootstrap": bool(bootstrap), "bootstrap_n": int(bootstrap_n) if bootstrap else 0}
    trace.update(res.trace or {})

    return CausalResult(query=query, estimate=e, trace=trace)
