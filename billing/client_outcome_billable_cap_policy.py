from __future__ import annotations

from dataclasses import dataclass

from billing.client_outcome_package_progress import ClientOutcomePackageProgress
from lead_outcomes.client_outcome_contract import BillableClientRecord

CANON_CLIENT_OUTCOME_BILLABLE_CAP_POLICY = True


@dataclass(frozen=True, slots=True)
class BillableCapDecision:
    allowed: bool
    reason_code: str


@dataclass(frozen=True, slots=True)
class ClientOutcomeBillableCapPolicy:
    def evaluate(self, *, progress: ClientOutcomePackageProgress, record: BillableClientRecord) -> BillableCapDecision:
        if int(record.quantity) <= 0:
            return BillableCapDecision(allowed=False, reason_code='non_positive_quantity')
        if float(record.unit_price) < 0.0 or float(record.amount) < 0.0:
            return BillableCapDecision(allowed=True, reason_code='negative_adjustment_allowed')
        if progress.closed:
            return BillableCapDecision(allowed=False, reason_code='package_billable_cap_reached')
        return BillableCapDecision(allowed=True, reason_code='billable_within_package_cap')
    decide = evaluate
