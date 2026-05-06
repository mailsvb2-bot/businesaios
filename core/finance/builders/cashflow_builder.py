
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from core.finance.enums import FinanceSnapshotStatus
from core.finance.ids import FinanceSnapshotId
from core.finance.types import CashflowSummary, FinanceSnapshot, LiquiditySnapshot, ProfitSummary, RevenueSummary


def build_cashflow_snapshot(tenant_id: str, revenue: float, expenses: float) -> FinanceSnapshot:
    built_at = datetime.now(UTC)
    settled_revenue = Decimal(str(revenue))
    operating_expense = Decimal(str(expenses))
    net_cashflow = settled_revenue - operating_expense
    revenue_summary = RevenueSummary(
        gross_revenue=settled_revenue,
        settled_revenue=settled_revenue,
        failed_revenue=Decimal('0'),
        revenue_by_source={'default': settled_revenue},
    )
    profit_summary = ProfitSummary(
        settled_revenue=settled_revenue,
        operating_expense=operating_expense,
        payouts=Decimal('0'),
        net_profit=net_cashflow,
    )
    cashflow_summary = CashflowSummary(
        settled_inflow=settled_revenue,
        payout_outflow=Decimal('0'),
        expense_outflow=operating_expense,
        total_outflow=operating_expense,
        net_cashflow=net_cashflow,
        ledger_balance=net_cashflow,
    )
    reserve_target = max(Decimal('0'), operating_expense * Decimal('0.2'))
    available_cash = cashflow_summary.ledger_balance
    reserve_gap = max(Decimal('0'), reserve_target - available_cash)
    ratio = Decimal('0') if reserve_target <= 0 else available_cash / reserve_target
    liquidity = LiquiditySnapshot(
        available_cash=available_cash,
        reserve_target=reserve_target,
        reserve_gap=reserve_gap,
        liquidity_ratio=ratio,
    )
    snapshot_id = FinanceSnapshotId(str(tenant_id))
    return FinanceSnapshot(
        snapshot_id=snapshot_id,
        built_at=built_at,
        window_start_at=built_at - timedelta(days=30),
        window_end_at=built_at,
        status=FinanceSnapshotStatus.OK,
        revenue_summary=revenue_summary,
        profit_summary=profit_summary,
        cashflow_summary=cashflow_summary,
        liquidity_snapshot=liquidity,
    )
