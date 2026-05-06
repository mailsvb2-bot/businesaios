from __future__ import annotations

from decimal import Decimal


class CashBufferPolicy:
    def should_hold(self, liquidity_balances: list[Decimal], min_buffer: Decimal) -> bool:
        return min(liquidity_balances, default=Decimal('0')) < min_buffer
