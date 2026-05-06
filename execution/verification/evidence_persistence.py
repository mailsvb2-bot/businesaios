from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from execution.verification.evidence_types import EvidenceItem
from execution.verification.verification_contract import VerificationDecision, VerificationRequest
CANON_VERIFICATION_EVIDENCE_PERSISTENCE = True
@dataclass(frozen=True, slots=True)
class VerificationPersistenceArtifacts:
    verification_record: dict[str, Any]
    evidence_records: tuple[dict[str, Any], ...]
    retry_record: dict[str, Any] | None = None
    def to_dict(self) -> dict[str, Any]:
        return {
            "verification_record": dict(self.verification_record),
            "evidence_records": [dict(item) for item in self.evidence_records],
            "retry_record": None if self.retry_record is None else dict(self.retry_record),
        }
class VerificationEvidencePersistence:
    def build_artifacts(
        self,
        *,
        request: VerificationRequest,
        decision: VerificationDecision,
        evidence: tuple[EvidenceItem, ...],
        retry_plan: dict[str, Any] | None = None,
    ) -> VerificationPersistenceArtifacts:
        verification_record = {
            "tenant_id": request.tenant_id,
            "business_id": request.business_id,
            "run_id": request.run_id,
            "step_index": request.step_index,
            "action_id": request.action_id,
            "action_type": request.action_type,
            "verified": decision.verified,
            "status": decision.status,
            "code": decision.code,
            "reason": decision.reason,
            "source_of_truth": decision.source_of_truth,
            "confidence": float(decision.confidence),
            "observed_external_refs": list(decision.observed_external_refs),
            "matched_evidence_ids": list(decision.matched_evidence_ids),
            "conflicting_evidence_ids": list(decision.conflicting_evidence_ids),
            "pending_evidence_ids": list(decision.pending_evidence_ids),
            "retryable": decision.retryable,
            "delayed": decision.delayed,
            "timed_out": decision.timed_out,
            "decision_fingerprint": decision.decision_fingerprint,
            "policy": dict(decision.policy_snapshot),
            "summary": dict(decision.summary),
            "decided_at": decision.decided_at.isoformat(),
        }
        evidence_records = tuple(
            {
                "tenant_id": request.tenant_id,
                "business_id": request.business_id,
                "run_id": request.run_id,
                "step_index": request.step_index,
                "action_id": request.action_id,
                "action_type": request.action_type,
                "evidence_id": item.evidence_id,
                "source": item.source,
                "kind": item.kind,
                "status": item.status,
                "external_refs": list(item.external_refs),
                "confidence": float(item.confidence),
                "observed_at": item.observed_at.isoformat(),
                "payload": dict(item.payload),
                "metadata": dict(item.metadata),
                "correlation_key": item.correlation_key(),
                "authoritative": item.is_authoritative(),
            }
            for item in evidence
        )
        return VerificationPersistenceArtifacts(
            verification_record=verification_record,
            evidence_records=evidence_records,
            retry_record=None if retry_plan is None else dict(retry_plan),
        )
__all__ = [
    "CANON_VERIFICATION_EVIDENCE_PERSISTENCE",
    "VerificationPersistenceArtifacts",
    "VerificationEvidencePersistence",
]
