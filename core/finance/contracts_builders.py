from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Protocol

from .contracts_window import FinanceWindow
from .enums import FinanceSnapshotStatus
from .ids import FinanceSnapshotId
from .types import CashflowSummary, FinanceSnapshot, LiquiditySnapshot, ProfitSummary, RevenueSummary


class CashflowBuilder(Protocol):
    def build(self, payments, payouts, expenses, ledger_entries) -> CashflowSummary: ...


class RevenueSummaryBuilder(Protocol):
    def build(self, revenues, payments) -> RevenueSummary: ...


class ProfitSummaryBuilder(Protocol):
    def build(self, revenue_summary, expenses, payouts) -> ProfitSummary: ...


class LiquiditySnapshotBuilder(Protocol):
    def build(self, ledger_balance: Decimal, reserve_target: Decimal) -> LiquiditySnapshot: ...


class FinanceSnapshotBuilder(Protocol):
    def build(
        self,
        snapshot_id: FinanceSnapshotId,
        built_at: datetime,
        window: FinanceWindow,
        status: FinanceSnapshotStatus,
        revenue_summary: RevenueSummary,
        profit_summary: ProfitSummary,
        cashflow_summary: CashflowSummary,
        liquidity_snapshot: LiquiditySnapshot,
    ) -> FinanceSnapshot: ...
