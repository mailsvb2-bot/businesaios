from __future__ import annotations

from dataclasses import dataclass

from ..enums import EconomicsSignalStatus, PaybackRiskLevel
from ..types import PaybackSnapshot


@dataclass
class PaybackRiskEvaluator:
    def evaluate(self, payback: PaybackSnapshot) -> EconomicsSignalStatus:
        return {
            PaybackRiskLevel.LOW: EconomicsSignalStatus.HEALTHY,
            PaybackRiskLevel.MODERATE: EconomicsSignalStatus.WARNING,
            PaybackRiskLevel.HIGH: EconomicsSignalStatus.WARNING,
            PaybackRiskLevel.SEVERE: EconomicsSignalStatus.CRITICAL,
        }.get(payback.risk_level, EconomicsSignalStatus.UNKNOWN)
