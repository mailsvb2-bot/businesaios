from __future__ import annotations

import math
from typing import Iterable


def pareto_top_share(values: Iterable[float], top_fraction: float = 0.2) -> float:
    """Share of total contributed by top_fraction of items."""
    xs = sorted([max(0.0, float(v)) for v in values], reverse=True)
    if not xs:
        return 0.0
    top_fraction = max(0.0, min(1.0, float(top_fraction)))
    k = max(1, int(math.ceil(len(xs) * top_fraction)))
    top_sum = sum(xs[:k])
    total = sum(xs)
    if total <= 0:
        return 0.0
    return top_sum / total


def fit_alpha_mle(samples: Iterable[float], xmin: float = 1.0) -> float:
    """Continuous power-law MLE for alpha:
      alpha = 1 + n / Σ ln(x_i / xmin), for x_i >= xmin
    """
    xmin = float(xmin)
    if xmin <= 0:
        raise ValueError("xmin must be > 0.")
    xs = [float(x) for x in samples if float(x) >= xmin]
    n = len(xs)
    if n == 0:
        return 0.0
    s = 0.0
    for x in xs:
        s += math.log(x / xmin)
    if s <= 0:
        return 0.0
    return 1.0 + (n / s)
