"""Governance-facing survival adapter (no monkeypatch).

Single source of truth for controller logic: survival/controller.py
This module provides a wrapper with assess/should_rollback for governance use.
It must not become a parallel survival brain.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from survival.controller import SurvivalController as _BaseController
from survival.controller import SurvivalVerdict


class GovernanceHealthState(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"


@dataclass(frozen=True)
class GovernanceHealthThresholds:
    degraded_reward_drop: float = 0.10
    critical_reward_drop: float = 0.30
    degraded_error_rate: float = 0.10
    critical_error_rate: float = 0.30


class GovernanceSurvivalAdapter:
    """Wrapper around SurvivalController adding governance health assessment."""

    def __init__(
        self,
        controller: _BaseController | None = None,
        thresholds: GovernanceHealthThresholds | None = None,
    ) -> None:
        self._controller = controller or _BaseController()
        self._thresholds = thresholds or GovernanceHealthThresholds()
        self._governance_last_health: GovernanceHealthState = GovernanceHealthState.HEALTHY

    def evaluate(self, *args: Any, **kwargs: Any) -> SurvivalVerdict:
        return self._controller.evaluate(*args, **kwargs)

    def assess(self, *, reward_drop: float, error_rate: float) -> GovernanceHealthState:
        try:
            rd = max(0.0, float(reward_drop))
        except (TypeError, ValueError):
            rd = 0.0
        try:
            er = max(0.0, float(error_rate))
        except (TypeError, ValueError):
            er = 0.0

        t = self._thresholds
        if er >= t.critical_error_rate or rd >= t.critical_reward_drop:
            health = GovernanceHealthState.CRITICAL
        elif er >= t.degraded_error_rate or rd >= t.degraded_reward_drop:
            health = GovernanceHealthState.DEGRADED
        else:
            health = GovernanceHealthState.HEALTHY

        self._governance_last_health = health
        return health

    def should_rollback(self) -> bool:
        return self._governance_last_health is GovernanceHealthState.CRITICAL


# Backward-compat: tests import SurvivalController expecting assess/should_rollback
SurvivalController = GovernanceSurvivalAdapter

__all__ = [
    "SurvivalController",
    "GovernanceSurvivalAdapter",
    "GovernanceHealthState",
    "GovernanceHealthThresholds",
]
