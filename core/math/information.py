from __future__ import annotations

import math
from typing import Iterable


def entropy(probabilities: Iterable[float], *, base: float = 2.0) -> float:
    """Shannon entropy: H = - Σ p(x) log p(x)"""
    if base <= 0:
        raise ValueError("base must be > 0.")
    h = 0.0
    for p in probabilities:
        p = float(p)
        if p < 0:
            raise ValueError("probabilities must be non-negative.")
        if p == 0:
            continue
        h -= p * (math.log(p) / math.log(base))
    return h
