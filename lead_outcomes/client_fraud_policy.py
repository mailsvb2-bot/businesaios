from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from lead_outcomes.client_outcome_contract import ClientProofEvent, FraudVerdict, OutcomeLead

CANON_CLIENT_FRAUD_POLICY = True


def _count_repeated(values: Iterable[str]) -> int:
    seen: dict[str, int] = {}
    for value in values:
        normalized = str(value or '').strip().casefold()
        if not normalized:
            continue
        seen[normalized] = seen.get(normalized, 0) + 1
    return max(seen.values(), default=0)


@dataclass(frozen=True, slots=True)
class ClientFraudPolicy:
    max_same_external_ref_count: int = 3
    max_same_identity_count: int = 2
    hard_block_score: float = 0.75

    def evaluate(self, *, lead: OutcomeLead, proofs: Iterable[ClientProofEvent], related_leads: Iterable[OutcomeLead]) -> FraudVerdict:
        items = tuple(proofs)
        signals: list[str] = []
        score = 0.0
        if _count_repeated(proof.external_ref for proof in items if proof.external_ref) > self.max_same_external_ref_count:
            signals.append('repeated_external_ref')
            score += 0.45
        identity = lead.identity_fingerprint()
        if identity:
            duplicates = sum(1 for item in related_leads if item.lead_id != lead.lead_id and item.identity_fingerprint() == identity)
            if duplicates >= self.max_same_identity_count:
                signals.append('duplicate_identity')
                score += 0.45
        if items and all(str(proof.source).casefold() == 'manual' for proof in items):
            signals.append('manual_only_proofs')
            score += 0.2
        fraud_score = min(1.0, round(score, 4))
        allowed = fraud_score < self.hard_block_score
        return FraudVerdict(
            lead_id=lead.lead_id,
            allowed=allowed,
            fraud_score=fraud_score,
            reason_code='fraud_risk_blocked' if not allowed else ('fraud_risk_allowed_with_flags' if signals else 'fraud_risk_clear'),
            triggered_signals=tuple(signals),
        )
    decide = evaluate
