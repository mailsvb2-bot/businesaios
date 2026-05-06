from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Iterable

from lead_outcomes.client_outcome_contract import ClientOutcomeOrder, ClientProofEvent, EligibilityVerdict, OutcomeLead

CANON_CLIENT_ELIGIBILITY_POLICY = True


@dataclass(frozen=True, slots=True)
class ClientEligibilityPolicy:
    def evaluate(self, *, order: ClientOutcomeOrder, lead: OutcomeLead, proofs: Iterable[ClientProofEvent], historical_leads: Iterable[OutcomeLead]) -> EligibilityVerdict:
        items = tuple(proofs)
        proof_kinds = {str(item.proof_type).casefold() for item in items if item.is_positive()}
        if order.package.require_crm_proof and not proof_kinds.intersection({'crm_won', 'crm_contact', 'crm_deal', 'booking_confirmed'}):
            return EligibilityVerdict(lead_id=lead.lead_id, eligible=False, reason_code='missing_required_crm_proof', category='unbillable')
        if order.package.require_payment_proof and not proof_kinds.intersection({'payment_paid', 'deposit_received', 'invoice_paid'}):
            return EligibilityVerdict(lead_id=lead.lead_id, eligible=False, reason_code='missing_required_payment_proof', category='unbillable')
        if not order.package.allow_returning_clients:
            cutoff = lead.captured_at - timedelta(days=order.package.new_client_window_days)
            identity = lead.identity_fingerprint()
            if identity:
                for historical in historical_leads:
                    if historical.business_id != lead.business_id or historical.lead_id == lead.lead_id:
                        continue
                    if historical.captured_at >= cutoff and historical.identity_fingerprint() == identity:
                        return EligibilityVerdict(lead_id=lead.lead_id, eligible=False, reason_code='returning_client_blocked', category='existing_client')
        return EligibilityVerdict(lead_id=lead.lead_id, eligible=True, reason_code='eligible_new_client', category='new_client')
    decide = evaluate
