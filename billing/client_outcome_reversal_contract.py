from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping

CANON_CLIENT_OUTCOME_REVERSAL_CONTRACT = True


def _text(value: object) -> str:
    return str(value or '').strip()


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

    def validate(self) -> None:
        if not _text(self.reversal_id):
            raise ValueError('reversal_id is required')
        if not _text(self.negative_record_id):
            raise ValueError('negative_record_id is required')
        if float(self.amount) < 0:
            raise ValueError('amount must be non-negative')
