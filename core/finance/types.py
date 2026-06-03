
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from collections.abc import Mapping

from .enums import ExpenseCategory, FinanceSnapshotStatus, PaymentStatus, PayoutStatus
from .ids import FinanceSnapshotId


@dataclass(frozen=True)
class RevenueRecord:
    occurred_at: datetime
    amount: Decimal
    source: str

@dataclass(frozen=True)
class PaymentRecord:
    occurred_at: datetime
    amount: Decimal
    status: PaymentStatus
    provider: str

@dataclass(frozen=True)
class PayoutRecord:
    occurred_at: datetime
    amount: Decimal
    status: PayoutStatus
    destination: str

@dataclass(frozen=True)
class ExpenseRecord:
    occurred_at: datetime
    amount: Decimal
    category: ExpenseCategory
    description: str

@dataclass(frozen=True)
class LedgerEntry:
    occurred_at: datetime
    delta: Decimal
    kind: str
    reference: str

@dataclass(frozen=True)
class CashflowSummary:
    settled_inflow: Decimal
    payout_outflow: Decimal
    expense_outflow: Decimal
    total_outflow: Decimal
    net_cashflow: Decimal
    ledger_balance: Decimal

@dataclass(frozen=True)
class RevenueSummary:
    gross_revenue: Decimal
    settled_revenue: Decimal
    failed_revenue: Decimal
    revenue_by_source: Mapping[str, Decimal]

@dataclass(frozen=True)
class ProfitSummary:
    settled_revenue: Decimal
    operating_expense: Decimal
    payouts: Decimal
    net_profit: Decimal

@dataclass(frozen=True)
class LiquiditySnapshot:
    available_cash: Decimal
    reserve_target: Decimal
    reserve_gap: Decimal
    liquidity_ratio: Decimal

@dataclass(frozen=True)
class CashflowProjection:
    days: int
    projected_net_cashflow: Decimal
    projected_available_cash: Decimal

@dataclass(frozen=True)
class RevenueProjection:
    days: int
    projected_revenue: Decimal
    projected_settled_revenue: Decimal

@dataclass(frozen=True)
class LiquidityProjection:
    days: int
    projected_liquidity_ratio: Decimal
    projected_reserve_gap: Decimal

@dataclass(frozen=True)
class ReservePolicyResult:
    keep_reserve: bool
    reserve_amount: Decimal

@dataclass(frozen=True)
class FinanceSnapshot:
    snapshot_id: FinanceSnapshotId
    built_at: datetime
    window_start_at: datetime
    window_end_at: datetime
    status: FinanceSnapshotStatus
    revenue_summary: RevenueSummary
    profit_summary: ProfitSummary
    cashflow_summary: CashflowSummary
    liquidity_snapshot: LiquiditySnapshot
