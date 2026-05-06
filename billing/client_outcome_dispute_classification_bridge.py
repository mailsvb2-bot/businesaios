from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Mapping, Any

from billing.dispute_policy import DisputeClassification, DisputePolicy
from lead_outcomes.client_outcome_contract import BillableClientRecord


CANON_CLIENT_OUTCOME_DISPUTE_CLASSIFICATION_BRIDGE = True


def _text(value: object) -> str:
    return str(value or '').strip()


@dataclass(frozen=True, slots=True)
class ClientOutcomeDisputeClassificationBridge:
    dispute_policy: DisputePolicy

    def build_payload(
        self,
        *,
        reason_code: str,
        record: BillableClientRecord,
        metadata: Mapping[str, object] | None = None,
    ) -> dict[str, Any]:
        reason = _text(reason_code)
        raw = dict(metadata or {})
        payload: dict[str, Any] = {
            'client_outcome_reason_code': reason,
            'duplicate_flag': reason in {'duplicate_client', 'not_new_client'},
            'existing_customer_flag': reason in {'not_new_client', 'duplicate_client'},
            'attribution_mismatch': reason == 'not_attributed_to_platform',
            'fraud_flag': reason == 'fraud_suspected',
            'missing_proof': reason == 'missing_proof',
            'manual_review': reason == 'manual_operator_review',
            'record_id': record.record_id,
            'lead_id': record.lead_id,
            'business_id': record.business_id,
            'order_id': record.order_id,
            **raw,
        }
        payload['evidence_fingerprint'] = self._evidence_fingerprint(payload)
        return payload

    def classify(
        self,
        *,
        reason_code: str,
        record: BillableClientRecord,
        metadata: Mapping[str, object] | None = None,
    ) -> DisputeClassification:
        payload = self.build_payload(reason_code=reason_code, record=record, metadata=metadata)
        return self.dispute_policy.classify(payload)

    def _evidence_fingerprint(self, payload: Mapping[str, object]) -> str:
        canonical = '|'.join(
            [
                _text(payload.get('record_id')),
                _text(payload.get('lead_id')),
                _text(payload.get('order_id')),
                _text(payload.get('client_outcome_reason_code')),
                _text(payload.get('business_id')),
            ]
        )
        return sha256(canonical.encode('utf-8')).hexdigest()
