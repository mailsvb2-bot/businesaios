from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping, Protocol

from runtime.demand_gravity.admin_view import serialize_demand_candidate
from runtime.demand_gravity.contracts import DemandCandidate, DemandSignal
from runtime.demand_gravity.decision_input import DemandCandidateDecisionInput
from runtime.demand_gravity.no_second_brain import assert_payload_has_no_decision_fields
from runtime.demand_gravity.validation import validate_demand_candidate, validate_demand_signal


@dataclass(frozen=True)
class DemandGravityEvent:
    event_id: str
    event_type: str
    tenant_id: str
    business_id: str
    correlation_id: str
    idempotency_key: str
    occurred_at: datetime
    payload: Mapping[str, Any]

    def to_record(self) -> dict[str, Any]:
        record = {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "tenant_id": self.tenant_id,
            "business_id": self.business_id,
            "correlation_id": self.correlation_id,
            "idempotency_key": self.idempotency_key,
            "occurred_at": self.occurred_at.isoformat(),
            "payload": dict(self.payload),
        }
        assert_payload_has_no_decision_fields(record)
        return record


class DemandGravityEventSink(Protocol):
    def append(self, event: DemandGravityEvent) -> str:
        ...


def _stable_event_id(*parts: str) -> str:
    digest = sha256("|".join(parts).encode()).hexdigest()[:32]
    return f"dge_{digest}"


def signal_received_event(signal: DemandSignal, *, correlation_id: str, occurred_at: datetime | None = None) -> DemandGravityEvent:
    validate_demand_signal(signal)
    occurred = occurred_at or datetime.now(timezone.utc)
    payload = {
        "signal_id": signal.signal_id,
        "kind": signal.kind.value,
        "channel": signal.channel.value,
        "source_ref": signal.source_ref,
        "normalized_text": signal.normalized_text,
        "confidence": signal.confidence,
        "raw_fingerprint": signal.raw_fingerprint,
        "decision_owner": "DecisionCore",
        "execution_allowed": False,
    }
    assert_payload_has_no_decision_fields(payload)
    return DemandGravityEvent(
        event_id=_stable_event_id(signal.tenant_id, signal.business_id, signal.signal_id, signal.raw_fingerprint, "received"),
        event_type="DemandSignalReceived",
        tenant_id=signal.tenant_id,
        business_id=signal.business_id,
        correlation_id=correlation_id,
        idempotency_key=f"demand-signal:{signal.tenant_id}:{signal.business_id}:{signal.signal_id}",
        occurred_at=occurred,
        payload=payload,
    )


def candidate_built_event(candidate: DemandCandidate) -> DemandGravityEvent:
    validate_demand_candidate(candidate)
    payload = {
        "candidate": serialize_demand_candidate(candidate),
        "decision_owner": "DecisionCore",
        "execution_allowed": False,
    }
    assert_payload_has_no_decision_fields(payload)
    return DemandGravityEvent(
        event_id=_stable_event_id(candidate.tenant_id, candidate.business_id, candidate.candidate_id, "built"),
        event_type="DemandCandidateBuilt",
        tenant_id=candidate.tenant_id,
        business_id=candidate.business_id,
        correlation_id=candidate.correlation_id,
        idempotency_key=f"demand-candidate-built:{candidate.idempotency_key}",
        occurred_at=candidate.created_at,
        payload=payload,
    )


def candidate_submitted_event(decision_input: DemandCandidateDecisionInput, *, decision_ref: str) -> DemandGravityEvent:
    payload = {
        "decision_input": decision_input.to_payload(),
        "decision_ref": decision_ref,
        "decision_owner": "DecisionCore",
        "execution_allowed": False,
    }
    assert_payload_has_no_decision_fields(payload)
    return DemandGravityEvent(
        event_id=_stable_event_id(decision_input.tenant_id, decision_input.business_id, decision_input.candidate_id, decision_ref, "submitted"),
        event_type="DemandCandidateSubmittedToDecisionCore",
        tenant_id=decision_input.tenant_id,
        business_id=decision_input.business_id,
        correlation_id=decision_input.correlation_id,
        idempotency_key=f"demand-candidate-submitted:{decision_input.idempotency_key}:{decision_ref}",
        occurred_at=decision_input.created_at,
        payload=payload,
    )


__all__ = [
    "DemandGravityEvent",
    "DemandGravityEventSink",
    "signal_received_event",
    "candidate_built_event",
    "candidate_submitted_event",
]
