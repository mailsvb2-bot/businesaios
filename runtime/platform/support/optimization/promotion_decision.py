from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromotionDecision:
    candidate_id: str
    approved: bool
    reason: str = ""


__all__ = ["PromotionDecision"]
