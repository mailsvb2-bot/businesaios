from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RolloutRule:
    name: str
    percentage: int


@dataclass(frozen=True)
class RolloutDecision:
    rule_name: str
    enabled: bool
    bucket: int
