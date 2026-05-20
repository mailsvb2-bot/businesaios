from __future__ import annotations

from datetime import datetime

from runtime.demand_gravity.contracts import CandidateWriteMode, DemandCandidate, DemandSignal
from runtime.demand_gravity.no_second_brain import assert_payload_has_no_decision_fields


def validate_demand_signal(signal: DemandSignal) -> None:
    if not signal.signal_id.strip():
        raise ValueError("demand_signal_id_required")
    if not signal.tenant_id.strip():
        raise ValueError("demand_signal_tenant_required")
    if not isinstance(signal.observed_at, datetime) or signal.observed_at.tzinfo is None:
        raise ValueError("demand_signal_observed_at_timezone_required")
    if not signal.source_ref.strip():
        raise ValueError("demand_signal_source_ref_required")
    if not signal.raw_fingerprint.strip():
        raise ValueError("demand_signal_fingerprint_required")
    if not 0.0 <= float(signal.confidence) <= 1.0:
        raise ValueError("demand_signal_confidence_out_of_bounds")


def validate_demand_candidate(candidate: DemandCandidate) -> None:
    if not candidate.candidate_id.startswith("dgc_"):
        raise ValueError("demand_candidate_id_invalid")
    if not candidate.tenant_id.strip():
        raise ValueError("demand_candidate_tenant_required")
    if candidate.created_at.tzinfo is None:
        raise ValueError("demand_candidate_created_at_timezone_required")
    if candidate.write_mode != CandidateWriteMode.ADVISORY_ONLY:
        raise PermissionError("demand_candidate_must_be_advisory_only")
    if candidate.payload.get("execution_allowed") is not False:
        raise PermissionError("demand_candidate_execution_forbidden")
    if candidate.payload.get("decision_owner") != "DecisionCore":
        raise PermissionError("demand_candidate_decision_owner_required")
    if not candidate.signal_ids:
        raise ValueError("demand_candidate_signals_required")
    if not candidate.evidence_refs:
        raise ValueError("demand_candidate_evidence_required")
    if not candidate.idempotency_key.strip():
        raise ValueError("demand_candidate_idempotency_key_required")
    if not candidate.correlation_id.strip():
        raise ValueError("demand_candidate_correlation_id_required")
    assert_payload_has_no_decision_fields(candidate.payload)
