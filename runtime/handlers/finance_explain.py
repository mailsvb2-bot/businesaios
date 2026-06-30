
from __future__ import annotations

from runtime.finance import FinanceSnapshot, explain_cashflow

CANON_THIN_HANDLER = True

def handle_finance_explain(snapshot: FinanceSnapshot) -> str:
    return explain_cashflow(snapshot)
