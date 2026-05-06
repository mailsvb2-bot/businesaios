from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from billing.refund_orchestrator import RefundRequest


CANON_CLIENT_OUTCOME_REFUND_REQUEST_BRIDGE = True


@dataclass(frozen=True, slots=True)
class ClientOutcomeRefundRequestBridge:
    """Converts a refund preview payload into a RefundRequest contract when possible."""

    def to_request(self, *, now: datetime, preview: Mapping[str, Any] | None) -> RefundRequest | None:
        if preview is None:
            return None
        tenant_id = str(preview.get('tenant_id') or '').strip()
        invoice_id = str(preview.get('invoice_id') or '').strip()
        user_id = str(preview.get('user_id') or '').strip()
        provider_name = str(preview.get('provider_name') or '').strip()
        currency = str(preview.get('currency') or '').strip()
        reason = str(preview.get('reason') or '').strip()
        amount_minor = int(preview.get('amount_minor') or 0)
        if not all([tenant_id, invoice_id, user_id, provider_name, currency, reason]) or amount_minor <= 0:
            return None
        metadata = dict(preview.get('metadata') or {})
        return RefundRequest(
            tenant_id=tenant_id,
            invoice_id=invoice_id,
            user_id=user_id,
            amount_minor=amount_minor,
            currency=currency,
            reason=reason,
            provider_name=provider_name,
            requested_at=now,
            idempotency_key=str(metadata.get('reversal_id') or metadata.get('original_billable_record_id') or invoice_id),
            metadata=metadata,
        )
