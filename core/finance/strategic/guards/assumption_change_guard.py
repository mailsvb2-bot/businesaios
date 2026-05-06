from __future__ import annotations

from decimal import Decimal

from core.finance.strategic.types import GuardResult


class AssumptionChangeGuard:
    def check(self, old_value: Decimal, new_value: Decimal, tolerance: Decimal) -> GuardResult:
        base = max(abs(old_value), Decimal("1"))
        relative = abs(new_value - old_value) / base
        if relative > tolerance:
            return GuardResult(False, "assumption_change_large", "assumption change exceeded tolerance", {"relative_change": str(relative)})
        return GuardResult(True, "assumption_change_ok", "assumption change within tolerance")
