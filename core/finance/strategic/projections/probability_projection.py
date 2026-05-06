from __future__ import annotations

from decimal import Decimal

from core.finance.strategic.decimal_utils import q2
from core.finance.strategic.types import Scenario


class ProbabilityProjection:
    def project(self, scenarios: tuple[Scenario, ...]) -> dict[str, Decimal]:
        total = sum((item.probability for item in scenarios), start=Decimal('0')) or Decimal('1')
        return {item.name: q2(item.probability / total) for item in scenarios}
