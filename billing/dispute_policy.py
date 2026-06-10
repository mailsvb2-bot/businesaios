from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

CANON_BILLING_DISPUTE_POLICY = True


@dataclass(frozen=True)
class DisputeClassification:
    case_type: str
    severity: str = 'medium'
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        if not str(self.case_type or '').strip():
            raise ValueError('case_type is required')
        if str(self.severity or '').strip().lower() not in {'low', 'medium', 'high'}:
            raise ValueError('severity must be low, medium, or high')


class DisputePolicy:
    def classify(self, payload: Mapping[str, object]) -> DisputeClassification:
        normalized = dict(payload or {})
        if bool(normalized.get('attribution_mismatch')) and bool(normalized.get('duplicate_flag')):
            result = DisputeClassification(case_type='compound_attribution_duplicate_challenge', severity='high', metadata={'owner': 'billing.dispute_policy'})
        elif bool(normalized.get('missing_proof')):
            result = DisputeClassification(case_type='evidence_gap_review', severity='medium', metadata={'owner': 'billing.dispute_policy'})
        elif bool(normalized.get('existing_customer_flag')):
            result = DisputeClassification(case_type='existing_customer_challenge', severity='medium', metadata={'owner': 'billing.dispute_policy'})
        elif bool(normalized.get('duplicate_flag')):
            result = DisputeClassification(case_type='duplicate_lead_challenge', severity='medium', metadata={'owner': 'billing.dispute_policy'})
        elif bool(normalized.get('attribution_mismatch')):
            result = DisputeClassification(case_type='attribution_challenge', severity='high', metadata={'owner': 'billing.dispute_policy'})
        else:
            result = DisputeClassification(case_type='general_review', severity='low', metadata={'owner': 'billing.dispute_policy'})
        result.validate()
        return result


__all__ = ['CANON_BILLING_DISPUTE_POLICY', 'DisputeClassification', 'DisputePolicy']
