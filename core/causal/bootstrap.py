from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable, List, Tuple
from collections.abc import Sequence


@dataclass(frozen=True)
class BootstrapResult:
    stderr: float
    ci95_low: float
    ci95_high: float
    samples: list[float]


def bootstrap_ci(
    values: Sequence[float],
    *,
    n_boot: int = 500,
    seed: int = 0,
) -> BootstrapResult:
    """Nonparametric bootstrap CI for the mean of values."""

    vals = [float(v) for v in values]
    n = len(vals)
    if n <= 1:
        return BootstrapResult(stderr=0.0, ci95_low=vals[0] if vals else 0.0, ci95_high=vals[0] if vals else 0.0, samples=[vals[0] if vals else 0.0])

    rnd = random.Random(int(seed))
    means: list[float] = []
    for _ in range(int(n_boot)):
        s = [vals[rnd.randrange(0, n)] for _ in range(n)]
        means.append(sum(s) / float(n))

    means_sorted = sorted(means)
    n_means = len(means_sorted)
    # FIX: use round() for high-end index to avoid systematic underestimation
    # of the 97.5th percentile. int(0.975 * 500) = 487 but the correct percentile
    # is at index 488 (which round() correctly gives).
    lo_idx = max(0, int(0.025 * n_means))
    hi_idx = min(n_means - 1, round(0.975 * n_means))
    lo = means_sorted[lo_idx]
    hi = means_sorted[hi_idx]
    m = sum(means) / float(len(means))
    var = sum((x - m) ** 2 for x in means) / float(max(1, len(means) - 1))
    return BootstrapResult(stderr=var ** 0.5, ci95_low=float(lo), ci95_high=float(hi), samples=means)
