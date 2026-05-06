from __future__ import annotations

from decimal import Decimal

from core.finance.strategic.types import GuardResult


class ForecastDriftGuard:
    def check(self, previous: Decimal, current: Decimal, tolerance: Decimal) -> GuardResult:
        base = max(abs(previous), Decimal("1"))
        relative = abs(current - previous) / base
        if relative > tolerance:
            return GuardResult(False, "forecast_drift", "forecast drift exceeded tolerance", {"relative_drift": str(relative)})
        return GuardResult(True, "forecast_stable", "forecast drift within tolerance")
