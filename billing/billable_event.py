from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BillableEvent:
    lead_fingerprint: str
    outcome_kind: str
    amount: float
    currency: str = 'RUB'
