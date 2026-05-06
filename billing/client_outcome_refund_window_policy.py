from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from lead_outcomes.client_outcome_contract import BillableClientRecord

CANON_CLIENT_OUTCOME_REFUND_WINDOW_POLICY = True


@dataclass(frozen=True, slots=True)
class RefundWindowDecision:
    allowed: bool
    reason_code: str
    expired: bool


@dataclass(frozen=True, slots=True)
class ClientOutcomeRefundWindowPolicy:
    refund_window_days: int = 14

    def evaluate(self, *, now: datetime, record: BillableClientRecord) -> RefundWindowDecision:
        cutoff = record.verified_at + timedelta(days=max(1, int(self.refund_window_days)))
        if now > cutoff:
            return RefundWindowDecision(allowed=False, reason_code='refund_window_expired', expired=True)
        return RefundWindowDecision(allowed=True, reason_code='within_refund_window', expired=False)
    decide = evaluate
