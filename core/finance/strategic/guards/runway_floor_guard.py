from __future__ import annotations

from decimal import Decimal

from core.finance.strategic.types import GuardResult


class RunwayFloorGuard:
    def check(self, runway_months: Decimal, floor: Decimal) -> GuardResult:
        if runway_months < floor:
            return GuardResult(False, "runway_floor_breached", "runway below floor", {"runway_months": str(runway_months), "floor": str(floor)})
        return GuardResult(True, "runway_ok", "runway above floor")
