from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from lead_outcomes.client_outcome_contract import AttributionVerdict, ClientOutcomeOrder, ClientProofEvent, OutcomeLead

CANON_CLIENT_ATTRIBUTION_POLICY = True


def _within_window(*, captured_at: datetime, occurred_at: datetime, days: int) -> bool:
    delta = occurred_at - captured_at
    return delta.total_seconds() >= 0 and delta <= __import__('datetime').timedelta(days=max(1, int(days)))


@dataclass(frozen=True, slots=True)
class ClientAttributionPolicy:
    require_tracking_token: bool = True
    require_identity_or_external_ref: bool = True

    def evaluate(self, *, order: ClientOutcomeOrder, lead: OutcomeLead, proofs: Iterable[ClientProofEvent]) -> AttributionVerdict:
        items = tuple(proofs)
        if self.require_tracking_token and not lead.tracking_token:
            return AttributionVerdict(lead_id=lead.lead_id, attributed=False, reason_code='missing_tracking_token', source_of_truth='client_attribution_policy', confidence=0.0)

        accepted_refs: list[str] = []
        identity_present = bool(lead.identity_fingerprint())
        for proof in items:
            if proof.lead_id != lead.lead_id or proof.business_id != lead.business_id:
                continue
            if not _within_window(captured_at=lead.captured_at, occurred_at=proof.occurred_at, days=order.package.attribution_window_days):
                continue
            if proof.external_ref:
                accepted_refs.append(proof.external_ref)

        if self.require_identity_or_external_ref and not identity_present and not accepted_refs:
            return AttributionVerdict(lead_id=lead.lead_id, attributed=False, reason_code='missing_identity_and_external_ref', source_of_truth='client_attribution_policy', confidence=0.15)

        return AttributionVerdict(
            lead_id=lead.lead_id,
            attributed=True,
            reason_code='origin_proof_satisfied',
            source_of_truth='client_attribution_policy',
            confidence=0.85 if accepted_refs else 0.65,
            external_refs=tuple(dict.fromkeys(accepted_refs)),
        )
    decide = evaluate
