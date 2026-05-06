from __future__ import annotations

from decimal import Decimal


class LiquidityRiskExplainer:
    def explain(self, min_balance: Decimal, floor: Decimal, *, bias: str | None = None) -> str:
        extra = f' Active bias: {bias}.' if bias else ''
        return f'Minimum liquidity {min_balance} versus floor {floor}.{extra}'
