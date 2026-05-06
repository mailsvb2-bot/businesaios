from __future__ import annotations

from core.finance.strategic.entities.entity_finance_model import EntityFinanceModel


class ConsolidationEngine:
    def consolidate(self, entities: list[EntityFinanceModel]) -> dict:
        return {
            'revenue': round(sum(item.revenue for item in entities), 2),
            'costs': round(sum(item.costs for item in entities), 2),
            'cash': round(sum(item.cash for item in entities), 2),
        }
