from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class EntityFinanceModel:
    entity: str
    revenue: Decimal
    costs: Decimal
    cash: Decimal
    currency: str = 'USD'
