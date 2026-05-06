from __future__ import annotations

from decimal import Decimal

from core.finance.strategic.types import GuardResult


class CapitalConcentrationGuard:
    def check(self, allocation: dict[str, Decimal], max_share: Decimal, total: Decimal | None = None) -> GuardResult:
        total_amount = total if total is not None else sum(allocation.values(), start=Decimal('0'))
        share = (max(allocation.values()) / total_amount) if allocation and total_amount > 0 else Decimal('0')
        ok = share <= max_share
        return GuardResult(ok=ok, code='capital_concentration', message='Capital concentration check completed.')
