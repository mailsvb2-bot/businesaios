"""Shared stratified propensity estimation utility.

Extracted from ipw.py and doubly_robust.py to eliminate code duplication (BUG #7).
Both estimators used identical _fit_stratified_propensity + _key implementations.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Sequence

from core.causal.types import CausalDataset


def stratum_key(cov: Mapping[str, Any], names: Sequence[str]) -> str:
    """Stable stratum key from covariate values."""
    return "|".join(f"{n}={str(cov.get(n))}" for n in names)


def fit_stratified_propensity(
    dataset: CausalDataset,
    names: Sequence[str],
    *,
    smoothing: float = 1.0,
) -> Dict[str, float]:
    """Fit stratified propensity p(T=1 | X=stratum) with optional Laplace smoothing.

    Args:
        dataset: validated CausalDataset
        names: covariate names to use for stratification
        smoothing: Laplace smoothing constant (0.0 = no smoothing, MLE)

    Returns:
        dict mapping stratum_key -> propensity in (0, 1)
    """
    counts: Dict[str, List[float]] = {}
    for r in dataset.rows:
        k = stratum_key(r.covariates, names)
        counts.setdefault(k, [0.0, 0.0])
        counts[k][0] += 1.0
        counts[k][1] += 1.0 if float(r.treatment) >= 0.5 else 0.0

    out: Dict[str, float] = {}
    for k, (n, nt) in counts.items():
        out[k] = (float(nt) + float(smoothing)) / (float(n) + 2.0 * float(smoothing))
    return out
