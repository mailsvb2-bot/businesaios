from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from billing.client_outcome_dispute_contract import ClientOutcomeDisputeCase
from registry.base_registry import BaseRegistry

CANON_CLIENT_OUTCOME_DISPUTE_STORE = True


class ClientOutcomeDisputeStore(BaseRegistry):
    def __init__(self) -> None:
        super().__init__(kind='client_outcome_dispute')

    def save(self, case: ClientOutcomeDisputeCase) -> None:
        case.validate()
        self.register(case.dispute_id, {
            'dispute_id': case.dispute_id,
            'tenant_id': case.tenant_id,
            'business_id': case.business_id,
            'order_id': case.order_id,
            'lead_id': case.lead_id,
            'billable_record_id': case.billable_record_id,
            'opened_at': case.opened_at.isoformat(),
            'opened_by': case.opened_by,
            'reason_code': case.reason_code,
            'status': case.status,
            'resolution_code': case.resolution_code,
            'notes': case.notes,
            'metadata': dict(case.metadata),
        })

    def get(self, dispute_id: str) -> dict[str, Any]:
        try:
            return dict(super().get(str(dispute_id)))
        except KeyError:
            return {}

    def find_duplicate_open_case(
        self,
        *,
        tenant_id: str,
        order_id: str,
        lead_id: str,
        billable_record_id: str,
        reason_code: str,
        evidence_fingerprint: str,
    ) -> dict[str, Any] | None:
        for _, row in self.items():
            item = dict(row)
            if item.get('tenant_id') != tenant_id or item.get('order_id') != order_id:
                continue
            if item.get('lead_id') != lead_id or item.get('billable_record_id') != billable_record_id:
                continue
            if item.get('reason_code') != reason_code:
                continue
            if str(item.get('status') or '') not in {'open', 'under_review', 'reversed'}:
                continue
            metadata = dict(item.get('metadata') or {})
            if str(metadata.get('evidence_fingerprint') or '') == evidence_fingerprint:
                return item
        return None

    def list_for_order(self, *, tenant_id: str, order_id: str) -> tuple[dict[str, Any], ...]:
        rows = []
        for _, row in self.items():
            item = dict(row)
            if item.get('tenant_id') == tenant_id and item.get('order_id') == order_id:
                rows.append(item)
        return tuple(rows)


@dataclass(frozen=True, slots=True)
class ClientOutcomeReversalStore:
    registry: BaseRegistry

    def save(self, reversal_payload: dict[str, Any]) -> None:
        self.registry.register(str(reversal_payload['reversal_id']), dict(reversal_payload))

    def find_by_original_record(self, *, tenant_id: str, original_billable_record_id: str) -> dict[str, Any] | None:
        for _, row in self.registry.items():
            item = dict(row)
            if item.get('tenant_id') == tenant_id and item.get('original_billable_record_id') == original_billable_record_id:
                return item
        return None

    def list_for_order(self, *, tenant_id: str, order_id: str) -> tuple[dict[str, Any], ...]:
        rows = []
        for _, row in self.registry.items():
            item = dict(row)
            if item.get('tenant_id') == tenant_id and item.get('order_id') == order_id:
                rows.append(item)
        return tuple(rows)
