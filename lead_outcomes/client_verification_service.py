from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Sequence

from lead_outcomes import OutcomeVerifier, VerificationEvidence
from lead_outcomes.client_attribution_policy import ClientAttributionPolicy
from lead_outcomes.client_eligibility_policy import ClientEligibilityPolicy
from lead_outcomes.client_fraud_policy import ClientFraudPolicy
from lead_outcomes.client_outcome_contract import BillableClientRecord, ClientOutcomeOrder, ClientProofEvent, OutcomeLead, VerifiedClientVerdict

CANON_CLIENT_VERIFICATION_SERVICE = True


@dataclass(frozen=True, slots=True)
class ClientVerificationService:
    attribution_policy: ClientAttributionPolicy
    fraud_policy: ClientFraudPolicy
    eligibility_policy: ClientEligibilityPolicy
    outcome_verifier: OutcomeVerifier

    def verify(self, *, now: datetime, order: ClientOutcomeOrder, lead: OutcomeLead, proofs: Iterable[ClientProofEvent], related_leads: Sequence[OutcomeLead], historical_leads: Sequence[OutcomeLead]) -> VerifiedClientVerdict:
        items = tuple(proofs)
        attribution = self.attribution_policy.evaluate(order=order, lead=lead, proofs=items)
        fraud = self.fraud_policy.evaluate(lead=lead, proofs=items, related_leads=related_leads)
        eligibility = self.eligibility_policy.evaluate(order=order, lead=lead, proofs=items, historical_leads=historical_leads)
        evidences: list[VerificationEvidence] = []
        for proof in items:
            if not proof.is_positive():
                continue
            kind = str(proof.proof_type).casefold()
            if kind in {'call_connected', 'booking_confirmed', 'crm_won', 'crm_contact', 'crm_deal'}:
                evidences.append(VerificationEvidence(kind='crm_synced', value=True, weight=1.0))
            elif kind in {'payment_paid', 'deposit_received', 'invoice_paid'}:
                evidences.append(VerificationEvidence(kind='payment_seen', value=True, weight=1.0))
            else:
                evidences.append(VerificationEvidence(kind=kind, value=True, weight=0.4))
        verification = self.outcome_verifier.verify(evidences)
        verified = bool(attribution.attributed and fraud.allowed and eligibility.eligible and verification.verified)
        billable = bool(verified and eligibility.category == 'new_client')
        return VerifiedClientVerdict(
            lead_id=lead.lead_id,
            verified=verified,
            billable=billable,
            reason_code='verified_billable_client' if billable else ('verified_non_billable_client' if verified else 'client_verification_rejected'),
            confidence=min(1.0, round((float(attribution.confidence) + float(1.0 - fraud.fraud_score) + float(verification.confidence)) / 3.0, 4)),
            attribution=attribution,
            fraud=fraud,
            eligibility=eligibility,
            proof_refs=tuple(dict.fromkeys([proof.external_ref for proof in items if proof.external_ref])),
        )

    def to_billable_record(self, *, now: datetime, order: ClientOutcomeOrder, lead: OutcomeLead, verdict: VerifiedClientVerdict) -> BillableClientRecord | None:
        if not verdict.billable:
            return None
        return BillableClientRecord(
            record_id=f'billable:{order.order_id}:{lead.lead_id}',
            tenant_id=lead.tenant_id,
            business_id=lead.business_id,
            order_id=order.order_id,
            lead_id=lead.lead_id,
            package_id=order.package.package_id,
            verified_at=now,
            unit_price=order.package.price_per_verified_client,
            currency=order.package.currency,
            quantity=1,
            metadata={'reason_code': verdict.reason_code, 'trust_tier': order.package.trust_tier, 'proof_refs': list(verdict.proof_refs), 'verification_confidence': verdict.confidence},
        )
