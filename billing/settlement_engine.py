from __future__ import annotations

from billing.billable_event import BillableEvent
from billing.outcome_tariff import OutcomeTariff


class SettlementEngine:
    def build_event(self, *, lead_fingerprint: str, outcome_kind: str, revenue_amount: float, tariff: OutcomeTariff) -> BillableEvent:
        amount = tariff.price_for(outcome_kind, revenue_amount)
        return BillableEvent(lead_fingerprint=lead_fingerprint, outcome_kind=outcome_kind, amount=amount)
