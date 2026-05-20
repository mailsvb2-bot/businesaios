from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from runtime.demand_gravity.admin_view import serialize_demand_candidate
from runtime.demand_gravity.contracts import DemandCandidate
from runtime.demand_gravity.no_second_brain import assert_payload_has_no_decision_fields
from runtime.demand_gravity.validation import validate_demand_candidate


@dataclass(frozen=True)
class DemandCandidateDecisionInput:
    input_id: str
    tenant_id: str
    business_id: str
    candidate_id: str
    goal_type: str
    source: str
    decision_owner: str
    execution_allowed: bool
    idempotency_key: str
    correlation_id: str
    evidence_refs: tuple[str, ...]
    created_at: datetime
    payload: Mapping[str, Any]

    def to_payload(self) -> dict[str, Any]:
        payload = {
            "input_id": self.input_id,
            "tenant_id": self.tenant_id,
            "business_id": self.business_id,
            "candidate_id": self.candidate_id,
            "goal_type": self.goal_type,
            "source": self.source,
            "decision_owner": self.decision_owner,
            "execution_allowed": self.execution_allowed,
            "idempotency_key": self.idempotency_key,
            "correlation_id": self.correlation_id,
            "evidence_refs": list(self.evidence_refs),
            "created_at": self.created_at.isoformat(),
            "payload": dict(self.payload),
        }
        assert_payload_has_no_decision_fields(payload)
        return payload


def build_decision_input(candidate: DemandCandidate) -> DemandCandidateDecisionInput:
    validate_demand_candidate(candidate)
    payload = {
        "candidate": serialize_demand_candidate(candidate),
        "decision_contract": {
            "decision_owner": "DecisionCore",
            "execution_allowed": False,
            "candidate_role": "advisory_input_only",
        },
    }
    assert_payload_has_no_decision_fields(payload)
    return DemandCandidateDecisionInput(
        input_id=f"demand-input:{candidate.tenant_id}:{candidate.business_id}:{candidate.candidate_id}",
        tenant_id=candidate.tenant_id,
        business_id=candidate.business_id,
        candidate_id=candidate.candidate_id,
        goal_type="demand_candidate_review",
        source="demand_gravity",
        decision_owner="DecisionCore",
        execution_allowed=False,
        idempotency_key=candidate.idempotency_key,
        correlation_id=candidate.correlation_id,
        evidence_refs=tuple(candidate.evidence_refs),
        created_at=candidate.created_at,
        payload=payload,
    )


__all__ = ["DemandCandidateDecisionInput", "build_decision_input"]
