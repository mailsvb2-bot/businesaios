from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass

from .types import DemandObservation


@dataclass(frozen=True)
class ElasticityEstimate:
    """Simple elasticity estimate around a reference price."""

    price: float
    elasticity: float
    method: str


def arc_elasticity(*, p0: float, q0: float, p1: float, q1: float) -> float:
    """Arc elasticity between two points."""
    p0 = float(p0)
    p1 = float(p1)
    q0 = float(q0)
    q1 = float(q1)
    dp = p1 - p0
    dq = q1 - q0
    pbar = (p0 + p1) / 2.0
    qbar = (q0 + q1) / 2.0
    if abs(dp) < 1e-12 or abs(qbar) < 1e-12 or abs(pbar) < 1e-12:
        return 0.0
    return float((dq / dp) * (pbar / qbar))


def point_elasticity_isoelastic(*, b: float) -> float:
    """For Q=a*P^b, point elasticity equals b."""
    return float(b)


def estimate_isoelastic_b(observations: Iterable[DemandObservation]) -> float | None:
    """Estimate b in log Q = log a + b log P."""
    xs = []
    ys = []
    for o in observations:
        p = float(o.price.amount)
        q = float(o.units)
        if p <= 0 or q <= 0:
            continue
        xs.append(math.log(p))
        ys.append(math.log(q))
    if len(xs) < 2:
        return None
    xbar = sum(xs) / len(xs)
    ybar = sum(ys) / len(ys)
    num = sum((x - xbar) * (y - ybar) for x, y in zip(xs, ys, strict=False))
    den = sum((x - xbar) ** 2 for x in xs)
    if den < 1e-18:
        return None
    b = num / den
    if not math.isfinite(b):
        return None
    return float(b)
