from __future__ import annotations

import math


def z_test_proportions(*, x1: int, n1: int, x2: int, n2: int) -> float:
    """Two-proportion z-test."""
    if n1 <= 0 or n2 <= 0:
        raise ValueError("n1 and n2 must be > 0.")
    p1 = float(x1) / float(n1)
    p2 = float(x2) / float(n2)
    p = float(x1 + x2) / float(n1 + n2)
    denom = math.sqrt(p * (1.0 - p) * (1.0 / n1 + 1.0 / n2))
    if denom <= 0:
        return 0.0
    return (p1 - p2) / denom


def z_to_pvalue_2sided(z: float) -> float:
    """Two-sided p-value from z using normal CDF approximation (erf)."""
    z = abs(float(z))
    phi = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
    return max(0.0, min(1.0, 2.0 * (1.0 - phi)))
