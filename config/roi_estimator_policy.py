from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass


@dataclass(frozen=True)
class ROIEstimatorPolicy:
    max_uplift_pct: float = 0.25
    min_confidence: float = 0.30
    medium_confidence: float = 0.45
    max_confidence: float = 0.80
    low_impressions_threshold: int = 50
    medium_impressions_threshold: int = 200
    default_uplift_pct: float = 0.05
    increase_impressions_uplift_pct: float = 0.08
    improve_ctr_uplift_pct: float = 0.10
    improve_cr_uplift_pct: float = 0.12
    double_winner_uplift_pct: float = 0.06
