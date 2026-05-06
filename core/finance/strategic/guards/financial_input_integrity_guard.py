from __future__ import annotations

from decimal import Decimal

from core.finance.strategic.types import FinancialInput, GuardResult


class FinancialInputIntegrityGuard:
    def check(self, finance_input: FinancialInput) -> GuardResult:
        ok = (
            finance_input.revenue >= Decimal("0")
            and finance_input.costs >= Decimal("0")
            and finance_input.cash >= Decimal("0")
            and finance_input.debt >= Decimal("0")
        )
        return GuardResult(ok=ok, code="INPUT_OK" if ok else "INPUT_FAIL", message="ok" if ok else "financial input invalid")
