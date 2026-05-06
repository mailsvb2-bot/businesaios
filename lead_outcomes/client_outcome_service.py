from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Sequence

from lead_outcomes.client_outcome_contract import BillableClientRecord, ClientOutcomeOrder, ClientProofEvent, OutcomeLead, VerifiedClientVerdict
from lead_outcomes.client_outcome_registry import ClientOutcomeRegistry
from lead_outcomes.client_verification_service import ClientVerificationService

CANON_CLIENT_OUTCOME_SERVICE = True


@dataclass(frozen=True, slots=True)
class ClientOutcomeServiceResult:
    verdict: VerifiedClientVerdict
    billable_record: BillableClientRecord | None
    registry_row: dict[str, object]


class ClientOutcomeService:
    def __init__(self, *, registry: ClientOutcomeRegistry, verification_service: ClientVerificationService) -> None:
        self._registry = registry
        self._verification_service = verification_service

    def evaluate_lead(self, *, now: datetime, order: ClientOutcomeOrder, lead: OutcomeLead, proofs: Iterable[ClientProofEvent], related_leads: Sequence[OutcomeLead], historical_leads: Sequence[OutcomeLead]) -> ClientOutcomeServiceResult:
        verdict = self._verification_service.verify(now=now, order=order, lead=lead, proofs=proofs, related_leads=related_leads, historical_leads=historical_leads)
        billable_record = self._verification_service.to_billable_record(now=now, order=order, lead=lead, verdict=verdict)
        row = {
            'tenant_id': lead.tenant_id,
            'business_id': lead.business_id,
            'order_id': order.order_id,
            'package_id': order.package.package_id,
            'tracking_token': lead.tracking_token,
            'source_channel': lead.source_channel,
            'verified': verdict.verified,
            'billable': verdict.billable,
            'reason_code': verdict.reason_code,
            'verification_confidence': verdict.confidence,
            'attributed': verdict.attribution.attributed,
            'attribution_reason_code': verdict.attribution.reason_code,
            'fraud_allowed': verdict.fraud.allowed,
            'fraud_score': verdict.fraud.fraud_score,
            'fraud_reason_code': verdict.fraud.reason_code,
            'eligibility_ok': verdict.eligibility.eligible,
            'eligibility_reason_code': verdict.eligibility.reason_code,
            'eligibility_category': verdict.eligibility.category,
            'proof_refs': list(verdict.proof_refs),
            'billable_record_id': None if billable_record is None else billable_record.record_id,
            'billable_amount': None if billable_record is None else billable_record.amount,
            'billable_currency': None if billable_record is None else billable_record.currency,
            'evaluated_at': now.isoformat(),
        }
        self._registry.update(lead.lead_id, row)
        return ClientOutcomeServiceResult(verdict=verdict, billable_record=billable_record, registry_row=row)
