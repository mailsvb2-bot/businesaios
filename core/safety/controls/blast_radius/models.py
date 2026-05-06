from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BlastRadiusEstimate:
    financial_amount: float = 0.0
    users_affected: int = 0
    records_affected: int = 0
    services_touched: int = 0


@dataclass(frozen=True)
class BlastRadiusBudget:
    financial_amount: float
    users_affected: int
    records_affected: int
    services_touched: int
