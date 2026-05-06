from __future__ import annotations

from decimal import Decimal

from core.finance.strategic.types import GuardResult


class LiquidityStressGuard:
    def check(self, liquidity_balances: list[Decimal], floor: Decimal) -> GuardResult:
        ok = min(liquidity_balances, default=Decimal('0')) >= floor
        return GuardResult(ok=ok, code='liquidity_stress', message='Liquidity stress check completed.')
