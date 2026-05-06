from __future__ import annotations

from decimal import Decimal

from core.finance.strategic.types import GuardResult


class UnitEconomicsIntegrityGuard:
    def check(self, ltv: Decimal, cac: Decimal) -> GuardResult:
        ok = ltv >= max(cac, Decimal('0'))
        return GuardResult(ok=ok, code='unit_economics', message='Unit economics integrity check completed.')
