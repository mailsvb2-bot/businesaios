from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from billing.client_outcome_reversal_contract import ClientOutcomeReversalRecord
from lead_outcomes.client_outcome_contract import BillableClientRecord

CANON_CLIENT_OUTCOME_NEGATIVE_USAGE_BUILDER = True


@dataclass(frozen=True, slots=True)
class ClientOutcomeNegativeUsageBuilder:
    def build_negative_record(self, *, now: datetime, original: BillableClientRecord, reason_code: str, amount: float | None = None) -> tuple[BillableClientRecord, ClientOutcomeReversalRecord]:
        original_amount = abs(float(original.amount))
        reversal_amount = original_amount if amount is None else round(abs(float(amount)), 2)
        if reversal_amount <= 0 or reversal_amount > original_amount:
            raise ValueError('reversal amount must be > 0 and <= original amount')

        negative_record = BillableClientRecord(
            record_id=f'{original.record_id}:reversal',
            tenant_id=original.tenant_id,
            business_id=original.business_id,
            order_id=original.order_id,
            lead_id=original.lead_id,
            package_id=original.package_id,
            verified_at=now,
            unit_price=-reversal_amount,
            currency=original.currency,
            quantity=1,
            metadata={**original.normalized_metadata(), 'reversal_of': original.record_id, 'reversal_reason_code': reason_code},
        )
        reversal = ClientOutcomeReversalRecord(
            reversal_id=f'reversal:{original.record_id}',
            tenant_id=original.tenant_id,
            business_id=original.business_id,
            order_id=original.order_id,
            lead_id=original.lead_id,
            original_billable_record_id=original.record_id,
            negative_record_id=negative_record.record_id,
            created_at=now,
            reason_code=reason_code,
            amount=reversal_amount,
            currency=original.currency,
            metadata={'package_id': original.package_id},
        )
        return negative_record, reversal
