from __future__ import annotations

from dataclasses import dataclass

from ..enums import EconomicsSignalStatus, MarginHealthStatus
from ..types import MarginSnapshot


@dataclass
class MarginHealthEvaluator:
    def evaluate(self, margin: MarginSnapshot) -> EconomicsSignalStatus:
        return {
            MarginHealthStatus.STRONG: EconomicsSignalStatus.HEALTHY,
            MarginHealthStatus.STABLE: EconomicsSignalStatus.HEALTHY,
            MarginHealthStatus.WEAK: EconomicsSignalStatus.WARNING,
            MarginHealthStatus.NEGATIVE: EconomicsSignalStatus.CRITICAL,
        }.get(margin.status, EconomicsSignalStatus.UNKNOWN)
