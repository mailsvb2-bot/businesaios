from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Assumption:
    key: str
    value: Decimal
    description: str = ''


AssumptionType = Assumption
