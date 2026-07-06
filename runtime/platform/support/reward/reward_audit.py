from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class RewardAuditRecord:
    reward: float
    details: Mapping[str, float]

__all__ = [
    "RewardAuditRecord",
]
