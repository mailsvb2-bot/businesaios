from __future__ import annotations

from decimal import Decimal

from core.finance.strategic.decimal_utils import q2


class WorkingCapitalProjection:
    def project(self, receivables: Decimal, payables: Decimal, inventory: Decimal = Decimal('0')) -> Decimal:
        return q2(receivables + inventory - payables)
