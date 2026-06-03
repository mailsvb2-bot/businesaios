from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping


@dataclass(frozen=True)
class RewardAuditRecord:
    reward: float
    details: Mapping[str, float]

__all__ = [
    "RewardAuditRecord",
]
