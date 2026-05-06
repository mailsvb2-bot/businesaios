from __future__ import annotations

from dataclasses import dataclass

from ..enums import PaybackRiskLevel
from ..types import CACSnapshot, PaybackSnapshot, UnitEconomics


@dataclass
class PaybackBuilder:
    def build(self, *, cac: CACSnapshot, unit_economics: UnitEconomics) -> PaybackSnapshot:
        if cac.blended_cac is None or unit_economics.contribution_per_customer_day <= 0:
            return PaybackSnapshot(cac_payback_days=None, risk_level=PaybackRiskLevel.SEVERE)
        payback_days = cac.blended_cac / unit_economics.contribution_per_customer_day
        if payback_days <= 90:
            risk = PaybackRiskLevel.LOW
        elif payback_days <= 180:
            risk = PaybackRiskLevel.MODERATE
        elif payback_days <= 270:
            risk = PaybackRiskLevel.HIGH
        else:
            risk = PaybackRiskLevel.SEVERE
        return PaybackSnapshot(cac_payback_days=payback_days, risk_level=risk)
