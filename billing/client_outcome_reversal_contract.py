from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping

from billing.money import legacy_float, money_decimal

CANON_CLIENT_OUTCOME_REVERSAL_CONTRACT = True


def _text(value: object) -> str:
    return str(value or "").strip()


@dataclass(frozen=True, slots=True)
class ClientOutcomeReversalRecord:
    reversal_id: str
    tenant_id: str
    business_id: str
    order_id: str
    lead_id: str
    original_billable_record_id: str
    negative_record_id: str
    created_at: datetime
    reason_code: str
    amount: float
    currency: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        amount = money_decimal(self.amount, name="amount")
        currency = _text(self.currency).upper()
        if not currency:
            raise ValueError("currency is required")
        object.__setattr__(self, "amount", legacy_float(amount, name="amount"))
        object.__setattr__(self, "currency", currency)

    def validate(self) -> None:
        if not _text(self.reversal_id):
            raise ValueError("reversal_id is required")
        if not _text(self.negative_record_id):
            raise ValueError("negative_record_id is required")
        money_decimal(self.amount, name="amount")
