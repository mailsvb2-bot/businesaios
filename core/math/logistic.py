from __future__ import annotations

import math


def sigmoid(x: float) -> float:
    """P = 1 / (1 + e^{-x}) (numerically stable)."""
    x = float(x)
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def logit(p: float) -> float:
    """logit(p) = ln(p/(1-p))"""
    p = float(p)
    eps = 1e-15
    p = max(eps, min(1.0 - eps, p))
    return math.log(p / (1.0 - p))
