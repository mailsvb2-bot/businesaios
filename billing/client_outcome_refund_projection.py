from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from billing.client_outcome_reversal_contract import ClientOutcomeReversalRecord
from lead_outcomes.client_outcome_contract import BillableClientRecord


CANON_CLIENT_OUTCOME_REFUND_PROJECTION = True


def _text(value: object) -> str:
    return str(value or '').strip()


@dataclass(frozen=True, slots=True)
class ClientOutcomeRefundProjection:
    """Builds a refund-orchestrator compatible preview when invoice/provider affinity is available.
    Does not execute refunds. It only exposes a safe, auditable bridge payload.
    """

    def build_preview(
        self,
        *,
        original_record: BillableClientRecord,
        reversal: ClientOutcomeReversalRecord,
        user_id: str,
    ) -> dict[str, Any] | None:
        metadata = dict(original_record.metadata)
        invoice_id = _text(metadata.get('invoice_id'))
        provider_name = _text(metadata.get('provider_name') or metadata.get('payment_provider'))
        if not invoice_id or not provider_name:
            return None
        amount_minor = int(round(abs(float(reversal.amount)) * 100))
        if amount_minor <= 0:
            return None
        return {
            'tenant_id': original_record.tenant_id,
            'invoice_id': invoice_id,
            'user_id': _text(user_id) or 'system',
            'amount_minor': amount_minor,
            'currency': reversal.currency,
            'reason': reversal.reason_code,
            'provider_name': provider_name,
            'metadata': {
                'source': 'client_outcome_refund_projection',
                'original_billable_record_id': original_record.record_id,
                'reversal_id': reversal.reversal_id,
                'lead_id': original_record.lead_id,
                'order_id': original_record.order_id,
            },
        }
