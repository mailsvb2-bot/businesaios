from __future__ import annotations

"""Holdout assignment (pure).

Used for causal inference and safe experimentation:
keep a stable control group to estimate uplift.
"""

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class HoldoutDecision:
    is_control: bool
    bucket: int


def assign_holdout(*, key: str, holdout_pct: int) -> HoldoutDecision:
    pct = max(0, min(100, int(holdout_pct)))
    h = hashlib.sha256(str(key).encode("utf-8")).hexdigest()
    bucket = int(h[:8], 16) % 100
    return HoldoutDecision(is_control=(bucket < pct), bucket=bucket)
