from __future__ import annotations

from dataclasses import dataclass

from application.business_autonomy.delayed_outcome_bridge import (
    BusinessAutonomyDelayedOutcomeBridge,
    DelayedOutcomeSweepResult,
)


@dataclass(frozen=True)
class BusinessAutonomyDelayedOutcomeSweeper:
    bridge: BusinessAutonomyDelayedOutcomeBridge

    @classmethod
    def default(cls) -> 'BusinessAutonomyDelayedOutcomeSweeper':
        return cls(bridge=BusinessAutonomyDelayedOutcomeBridge.default())

    def sweep(self) -> DelayedOutcomeSweepResult:
        return self.bridge.sweep_expired()


__all__ = ['BusinessAutonomyDelayedOutcomeSweeper']
