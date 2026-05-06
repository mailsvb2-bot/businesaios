from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from lead_outcomes.client_outcome_contract import BillableClientRecord
from registry.base_registry import BaseRegistry

CANON_CLIENT_OUTCOME_USAGE_LEDGER = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


class ClientOutcomeUsageLedger(BaseRegistry):
    def __init__(self) -> None:
        super().__init__(kind='client_outcome_usage')

    def has_usage(self, record_id: str) -> bool:
        return str(record_id) in self.snapshot()

    def append_usage(self, record: BillableClientRecord) -> None:
        if self.has_usage(record.record_id):
            return
        self.register(record.record_id, {
            'record_id': record.record_id,
            'tenant_id': record.tenant_id,
            'business_id': record.business_id,
            'order_id': record.order_id,
            'lead_id': record.lead_id,
            'package_id': record.package_id,
            'verified_at': record.verified_at.isoformat(),
            'unit_price': record.unit_price,
            'quantity': record.quantity,
            'amount': record.amount,
            'currency': record.currency,
            'metadata': record.normalized_metadata(),
        })

    def list_usage(self) -> tuple[dict[str, Any], ...]:
        return tuple(_safe_dict(value) for _, value in self.items())


@dataclass(frozen=True, slots=True)
class ClientOutcomeUsageAppender:
    ledger: ClientOutcomeUsageLedger

    def append(self, record: BillableClientRecord) -> bool:
        if self.ledger.has_usage(record.record_id):
            return False
        self.ledger.append_usage(record)
        return True
