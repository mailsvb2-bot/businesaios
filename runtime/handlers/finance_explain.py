
from __future__ import annotations

CANON_THIN_HANDLER = True

from runtime.finance import FinanceSnapshot, explain_cashflow


def handle_finance_explain(snapshot: FinanceSnapshot) -> str:
    return explain_cashflow(snapshot)
