from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping

CANON_CLIENT_OUTCOME_DISPUTE_CONTRACT = True

_ALLOWED_STATUSES = {'open', 'under_review', 'accepted', 'rejected', 'reversed', 'expired'}
_ALLOWED_REASONS = {'not_new_client', 'fraud_suspected', 'not_attributed_to_platform', 'duplicate_client', 'missing_proof', 'service_not_rendered', 'manual_operator_review'}


def _text(value: object) -> str:
    return str(value or '').strip()


@dataclass(frozen=True, slots=True)
class ClientOutcomeDisputeCase:
    dispute_id: str
    tenant_id: str
    business_id: str
    order_id: str
    lead_id: str
    billable_record_id: str
    opened_at: datetime
    opened_by: str
    reason_code: str
    status: str = 'open'
    resolution_code: str = ''
    notes: str = ''
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not _text(self.dispute_id):
            raise ValueError('dispute_id is required')
        if not _text(self.tenant_id):
            raise ValueError('tenant_id is required')
        if not _text(self.business_id):
            raise ValueError('business_id is required')
        if not _text(self.order_id):
            raise ValueError('order_id is required')
        if not _text(self.lead_id):
            raise ValueError('lead_id is required')
        if not _text(self.billable_record_id):
            raise ValueError('billable_record_id is required')
        if not _text(self.opened_by):
            raise ValueError('opened_by is required')
        if _text(self.reason_code) not in _ALLOWED_REASONS:
            raise ValueError('unsupported reason_code')
        if _text(self.status) not in _ALLOWED_STATUSES:
            raise ValueError('unsupported status')
