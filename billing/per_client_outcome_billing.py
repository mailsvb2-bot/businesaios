from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from billing.billable_event import BillableEvent
from billing.usage_meter import UsageRecord
from lead_outcomes.client_outcome_contract import BillableClientRecord

CANON_PER_CLIENT_OUTCOME_BILLING = True


@dataclass(frozen=True, slots=True)
class PerClientOutcomeBillingProjector:
    meter_key: str = 'verified_client'

    def to_usage_record(self, record: BillableClientRecord) -> UsageRecord:
        return UsageRecord(
            tenant_id=record.tenant_id,
            meter_key=self.meter_key,
            quantity=float(record.quantity),
            idempotency_key=record.record_id,
            labels={'business_id': record.business_id, 'package_id': record.package_id, 'currency': record.currency},
            metadata={'resource_id': record.lead_id, 'order_id': record.order_id, 'verified_at': record.verified_at.isoformat(), 'unit_price': record.unit_price, **record.normalized_metadata()},
        )

    def to_billable_event(self, record: BillableClientRecord) -> BillableEvent:
        return BillableEvent(lead_fingerprint=record.lead_id, outcome_kind=self.meter_key, amount=record.amount, currency=record.currency)

    def project_usage(self, records: Iterable[BillableClientRecord]) -> tuple[UsageRecord, ...]:
        return tuple(self.to_usage_record(item) for item in records)
