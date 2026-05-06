from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

class Constraints:
    def valid_probability(self, value: float) -> bool:
        return 0.0 <= value <= 1.0

    def non_negative(self, value: float) -> bool:
        return value >= 0.0

class Guard(Protocol):
    def allows(self, payload: dict) -> bool:
        ...

INCIDENT_TYPES = (
    "reward_hacking",
    "runaway_feedback",
    "unsafe_action",
    "drift",
    "constraint_violation",
)

class LimitRegistry:
    def __init__(self) -> None:
        self._limits: dict[str, float] = {}

    def set(self, name: str, value: float) -> None:
        self._limits[name] = value

    def get(self, name: str) -> float:
        return self._limits[name]

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class RuleRegistry:
    def __init__(self) -> None:
        self._rules: dict[str, object] = {}

    def register(self, name: str, rule: object) -> None:
        self._rules[name] = rule

    def get(self, name: str) -> object:
        return self._rules[name]

SAFE_DEFAULTS = {
    "max_cost": 0.0,
    "unsafe": True,
    "approved": False,
    "reproducible": False,
}

@dataclass(frozen=True)
class SafetyPolicy:
    fail_closed: bool = True
    require_human_override_for_emergency: bool = True

VIOLATION_TYPES = (
    "promotion_without_evaluation",
    "serving_side_selection",
    "training_side_release",
    "hidden_objective_shift",
    "unsafe_runtime_action",
)

_ALIAS_EXPORTS = {
    "constraints": "Constraints",
    "contracts": "Guard",
    "incident_types": "INCIDENT_TYPES",
    "limit_registry": "LimitRegistry",
    "risk_levels": "RiskLevel",
    "rule_registry": "RuleRegistry",
    "safe_defaults": "SAFE_DEFAULTS",
    "safety_policy": "SafetyPolicy",
    "violation_types": "VIOLATION_TYPES",
}

__all__ = [
    "Constraints",
    "Guard",
    "INCIDENT_TYPES",
    "LimitRegistry",
    "RiskLevel",
    "RuleRegistry",
    "SAFE_DEFAULTS",
    "SafetyPolicy",
    "VIOLATION_TYPES",
]
