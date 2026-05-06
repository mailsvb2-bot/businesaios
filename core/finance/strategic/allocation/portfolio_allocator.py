from __future__ import annotations

from decimal import Decimal


class PortfolioAllocator:
    def merge(
        self,
        capital: dict[str, Decimal],
        budget: dict[str, Decimal],
        channels: dict[str, Decimal],
    ) -> dict[str, dict[str, Decimal]]:
        return {
            'capital': dict(capital),
            'budget': dict(budget),
            'channels': dict(channels),
        }
