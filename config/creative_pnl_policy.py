from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass


@dataclass(frozen=True)
class CreativePnLPolicy:
    min_cost: float = 0.0
    min_revenue_for_margin: float = 0.0
    min_total_cost_for_roi: float = 0.0
    min_margin_ratio: float = -1.0
    max_margin_ratio: float = 1.0
    default_margin_ratio: float = 0.0
    default_roi: float = 0.0


DEFAULT_CREATIVE_PNL_POLICY = CreativePnLPolicy()
