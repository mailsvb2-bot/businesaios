from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass


@dataclass(frozen=True)
class GovernanceReviewPolicy:
    risk_review_threshold: float = 0.70
