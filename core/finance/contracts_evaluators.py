from __future__ import annotations

from decimal import Decimal
from typing import Protocol
from collections.abc import Sequence

from .types import LiquiditySnapshot, PaymentRecord, RevenueRecord


class LiquidityRiskEvaluator(Protocol):
    def evaluate(self, snapshot: LiquiditySnapshot) -> Decimal: ...


class RevenueVolatilityEvaluator(Protocol):
    def evaluate(self, revenues: Sequence[RevenueRecord]) -> Decimal: ...


class PaymentFailureEvaluator(Protocol):
    def evaluate(self, payments: Sequence[PaymentRecord]) -> Decimal: ...
