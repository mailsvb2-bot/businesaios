from __future__ import annotations
CANON_THIN_HANDLER = True
from runtime.finance import FinanceSnapshot, build_cashflow_snapshot

def handle_finance_build(tenant_id: str, revenue: float, expenses: float) -> FinanceSnapshot:
    return build_cashflow_snapshot(tenant_id=tenant_id, revenue=revenue, expenses=expenses)
