
from __future__ import annotations

from core.finance.types import FinanceSnapshot


def explain_cashflow(snapshot: FinanceSnapshot) -> str:
    revenue = snapshot.revenue_summary.settled_revenue
    expenses = snapshot.profit_summary.operating_expense
    cashflow = snapshot.cashflow_summary.net_cashflow
    reserve_gap = snapshot.liquidity_snapshot.reserve_gap
    return (
        f'revenue={revenue}; '
        f'expenses={expenses}; '
        f'cashflow={cashflow}; '
        f'reserve_gap={reserve_gap}'
    )
