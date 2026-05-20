from __future__ import annotations

from datetime import datetime
from typing import Any

from runtime.demand_gravity.contracts import DemandCandidate


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


def serialize_demand_candidate(candidate: DemandCandidate) -> dict[str, Any]:
    return {
        "candidate_id": candidate.candidate_id,
        "tenant_id": candidate.tenant_id,
        "business_id": candidate.business_id,
        "channel": candidate.channel.value,
        "signal_ids": list(candidate.signal_ids),
        "write_mode": candidate.write_mode.value,
        "evidence_refs": list(candidate.evidence_refs),
        "created_at": candidate.created_at.isoformat(),
        "payload": _jsonable(dict(candidate.payload)),
        "idempotency_key": candidate.idempotency_key,
        "correlation_id": candidate.correlation_id,
    }


def build_demand_gravity_admin_view(*, tenant_id: str, candidates: tuple[DemandCandidate, ...], decision_refs: tuple[str, ...] = ()) -> dict[str, Any]:
    business_ids = sorted({candidate.business_id for candidate in candidates if candidate.business_id})
    return {
        "tenant_id": tenant_id,
        "business_ids": business_ids,
        "surface": "demand_gravity",
        "role": "signal_candidate_producer_only",
        "decision_owner": "DecisionCore",
        "execution_owner": "canonical_execution_pipeline",
        "second_brain_status": "blocked_by_contract",
        "decision_input_contract": {
            "input_type": "DemandCandidateDecisionInput",
            "goal_type": "demand_candidate_review",
            "execution_allowed": False,
            "decision_owner": "DecisionCore",
            "idempotency_required": True,
            "evidence_required": True,
        },
        "event_contracts": [
            "DemandSignalReceived",
            "DemandCandidateBuilt",
            "DemandCandidateSubmittedToDecisionCore",
        ],
        "candidates": [serialize_demand_candidate(candidate) for candidate in candidates],
        "decision_refs": list(decision_refs),
        "hard_guards": {
            "can_decide": False,
            "can_execute": False,
            "can_rank_channels": False,
            "can_allocate_budget": False,
            "can_mutate_external_platforms": False,
            "requires_business_scope": True,
            "requires_decision_core": True,
            "requires_evidence": True,
            "requires_admin_visibility": True,
        },
    }
