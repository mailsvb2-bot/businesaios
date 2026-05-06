from __future__ import annotations

from typing import Protocol, Sequence

from .contracts_window import FinanceWindow
from .types import ExpenseRecord, LedgerEntry, PaymentRecord, PayoutRecord, RevenueRecord


class RevenueReader(Protocol):
    def read_revenue(self, window: FinanceWindow) -> Sequence[RevenueRecord]: ...


class PaymentReader(Protocol):
    def read_payments(self, window: FinanceWindow) -> Sequence[PaymentRecord]: ...


class PayoutReader(Protocol):
    def read_payouts(self, window: FinanceWindow) -> Sequence[PayoutRecord]: ...


class ExpenseReader(Protocol):
    def read_expenses(self, window: FinanceWindow) -> Sequence[ExpenseRecord]: ...


class LedgerReader(Protocol):
    def read_ledger_entries(self, window: FinanceWindow) -> Sequence[LedgerEntry]: ...
