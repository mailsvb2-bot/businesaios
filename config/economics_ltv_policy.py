from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass


@dataclass(frozen=True)
class LTVBuilderPolicy:
    zero_amount: float = 0.0
    default_margin_ratio: float = 0.5
    minimum_retention: float = 0.01
    maximum_retention: float = 0.999
    default_horizon_months: int = 12


DEFAULT_LTV_BUILDER_POLICY = LTVBuilderPolicy()
