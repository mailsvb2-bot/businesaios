from __future__ import annotations

from decimal import Decimal

from core.finance.strategic.decimal_utils import q2


class RunwayProjection:
    def project(self, cash: Decimal, burn_rate: list[Decimal]) -> Decimal:
        avg_burn = (sum(burn_rate, start=Decimal("0")) / Decimal(len(burn_rate))) if burn_rate else Decimal("0")
        if avg_burn <= 0:
            return Decimal("999999")
        return q2(cash / avg_burn)
