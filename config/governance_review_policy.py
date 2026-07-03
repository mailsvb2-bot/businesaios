from __future__ import annotations

from dataclasses import dataclass

CANON_COMPAT_SHIM = True

@dataclass(frozen=True)
class GovernanceReviewPolicy:
    risk_review_threshold: float = 0.70
