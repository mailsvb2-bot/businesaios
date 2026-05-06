from __future__ import annotations

from core.finance.strategic.types import FinancialInput


class EntitySnapshotBuilder:
    def build(self, finance_input: FinancialInput) -> dict:
        return {
            'entities': list(finance_input.entities),
            'cash': finance_input.cash,
            'revenue': finance_input.revenue,
            'costs': finance_input.costs,
        }
