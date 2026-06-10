from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from billing.client_outcome_reversal_contract import ClientOutcomeReversalRecord
from billing.ledger_event import LedgerEntry, LedgerPosting

CANON_CLIENT_OUTCOME_REVERSAL_LEDGER_BRIDGE = True


@dataclass(frozen=True, slots=True)
class ClientOutcomeReversalLedgerBridge:
    contra_revenue_account: str = 'billing.accounts.refunds'
    receivable_account: str = 'billing.accounts.accounts_receivable'

    def build_posting(self, *, reversal: ClientOutcomeReversalRecord, booked_at: datetime) -> LedgerPosting:
        if booked_at.tzinfo is None:
            raise ValueError('booked_at must be timezone-aware')
        amount_minor = int(round(float(reversal.amount) * 100.0))
        reference_id = reversal.reversal_id
        debit = LedgerEntry(
            tenant_id=reversal.tenant_id,
            entry_id=f'{reference_id}:debit',
            account_code=self.contra_revenue_account,
            side='debit',
            amount_minor=amount_minor,
            currency=reversal.currency,
            reference_type='client_outcome_reversal',
            reference_id=reference_id,
            booked_at=booked_at,
            metadata={'order_id': reversal.order_id, 'lead_id': reversal.lead_id},
        )
        credit = LedgerEntry(
            tenant_id=reversal.tenant_id,
            entry_id=f'{reference_id}:credit',
            account_code=self.receivable_account,
            side='credit',
            amount_minor=amount_minor,
            currency=reversal.currency,
            reference_type='client_outcome_reversal',
            reference_id=reference_id,
            booked_at=booked_at,
            metadata={'order_id': reversal.order_id, 'lead_id': reversal.lead_id},
        )
        posting = LedgerPosting(
            posting_id=f'posting:{reference_id}',
            tenant_id=reversal.tenant_id,
            reference_type='client_outcome_reversal',
            reference_id=reference_id,
            entries=(debit, credit),
            metadata={'reason_code': reversal.reason_code, 'original_billable_record_id': reversal.original_billable_record_id},
        )
        posting.validate()
        return posting
