from __future__ import annotations

from decimal import Decimal

from core.finance.strategic.decimal_utils import q2
from core.finance.strategic.entities.entity_finance_model import EntityFinanceModel


class CurrencyTranslationService:
    def translate(self, entity: EntityFinanceModel, fx_rate: Decimal, target_currency: str) -> EntityFinanceModel:
        return EntityFinanceModel(
            entity=entity.entity,
            revenue=q2(entity.revenue * fx_rate),
            costs=q2(entity.costs * fx_rate),
            cash=q2(entity.cash * fx_rate),
            currency=target_currency,
        )
