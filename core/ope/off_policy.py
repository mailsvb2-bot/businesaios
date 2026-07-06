"""Off-policy evaluation (OPE) primitives.

Implements standard estimators for logged bandit data:
  - IPS (inverse propensity scoring)
  - WIS (weighted IPS)

Inputs are simple dict-like mappings to avoid tight coupling.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class OPEStats:
    n: int
    ips: float
    wis: float


def evaluate_ips(*, logged: Iterable[Mapping], min_propensity: float = 1e-6) -> OPEStats:
    total_r = 0.0
    w_sum = 0.0
    w_r_sum = 0.0
    n = 0

    for row in logged:
        n += 1
        r = float(row.get("reward") or 0.0)
        p = float(row.get("logged_propensity") or 0.0)
        q = float(row.get("target_propensity") or 0.0)
        p = max(float(min_propensity), p)
        w = q / p
        total_r += w * r
        w_sum += w
        w_r_sum += w * r

    ips = (total_r / float(n)) if n > 0 else 0.0
    wis = (w_r_sum / w_sum) if w_sum > 0 else 0.0
    return OPEStats(n=int(n), ips=float(ips), wis=float(wis))
