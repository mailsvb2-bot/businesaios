from __future__ import annotations

from decimal import Decimal

from core.finance.strategic.decimal_utils import q2
from core.finance.strategic.types import FinancialInput


class RetentionAdjustedMarginBuilder:
    def build(self, finance_input: FinancialInput) -> Decimal:
        retention = Decimal('1') - finance_input.churn_rate
        return q2(finance_input.gross_margin_rate * retention)
