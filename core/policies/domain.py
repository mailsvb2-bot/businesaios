from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PolicyStatus(str, Enum):
    CANDIDATE = "candidate"
    SHADOW = "shadow"
    CANARY = "canary"
    SAFE = "safe"
    ROLLED_BACK = "rolled_back"
    REJECTED = "rejected"


@dataclass(frozen=True)
class PolicyRef:
    policy_id: str
    version: str


@dataclass(frozen=True)
class RolloutConfig:
    canary_pct: float
    min_decisions: int
    max_error_rate: float
    auto_promote: bool = True
