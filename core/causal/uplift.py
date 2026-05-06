from __future__ import annotations

"""Minimal uplift estimator (small & dumb).

Placeholder for a full causal stack.
Provides difference-in-means uplift with basic safety.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class UpliftEstimate:
    uplift: float
    treated_rate: float
    control_rate: float


def diff_in_means(
    *,
    treated_success: int,
    treated_total: int,
    control_success: int,
    control_total: int,
) -> UpliftEstimate:
    t_tot = max(0, int(treated_total))
    c_tot = max(0, int(control_total))
    t_rate = (float(treated_success) / float(t_tot)) if t_tot > 0 else 0.0
    c_rate = (float(control_success) / float(c_tot)) if c_tot > 0 else 0.0
    return UpliftEstimate(uplift=float(t_rate - c_rate), treated_rate=float(t_rate), control_rate=float(c_rate))
