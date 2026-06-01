from __future__ import annotations

from dataclasses import dataclass

from config.system_config import CANONICAL_OBJECTIVE_NAME, RuntimeLimits

_ZERO = 0.0
_ONE = float(True)
_RUNTIME_LIMITS = RuntimeLimits()


@dataclass(frozen=True)
class DecisionConstraints:
    max_budget_delta: float = _RUNTIME_LIMITS.max_budget_delta
    min_confidence: float = _RUNTIME_LIMITS.min_confidence
    max_risk_score: float = _RUNTIME_LIMITS.max_risk_score
    forbidden_channels: tuple[str, ...] = ()
    objective_name: str = CANONICAL_OBJECTIVE_NAME

    def validate(self) -> None:
        if self.objective_name != CANONICAL_OBJECTIVE_NAME:
            raise ValueError(f"non-canonical objective requested: {self.objective_name}")
        if self.max_budget_delta < _ZERO:
            raise ValueError("max_budget_delta must be non-negative")
        if not _ZERO <= self.min_confidence <= _ONE:
            raise ValueError("min_confidence must be within inclusive normalized range")
        if not _ZERO <= self.max_risk_score <= _ONE:
            raise ValueError("max_risk_score must be within inclusive normalized range")
