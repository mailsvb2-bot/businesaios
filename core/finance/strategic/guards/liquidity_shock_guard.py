from __future__ import annotations

from decimal import Decimal

from core.finance.strategic.types import GuardResult


class LiquidityShockGuard:
    def check(self, balances: list[Decimal], shock_floor: Decimal) -> GuardResult:
        ok = min(balances, default=Decimal('0')) >= shock_floor
        return GuardResult(ok=ok, code='liquidity_shock', message='Liquidity shock check completed.')
