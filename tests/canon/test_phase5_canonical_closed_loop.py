from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any

import pytest

from application.business_autonomy.channel_contracts import ChannelIdentity, ChannelKind
from application.business_autonomy.evidence_projection import (
    ExternalBusinessFactIngress,
    NormalizedExternalBusinessFact,
)
from application.decision_runtime.emission import project_decision_proposed_event
from application.decision_state.world_model_metadata import attach_world_model_metadata
from application.evidence.evidence_persistence import EvidencePersistenceService
from application.headless.decision_gateway import issue_headless_decision
from application.headless.goal_mapper import HeadlessGoalStateMapper
from application.headless.models import GoalExecutionRequest
from contracts.business_outcome import BusinessOutcomeV1
from contracts.policy_decision import PolicyDecisionV1
from core.ai.decision_core import project_action_intent
from core.events.event_types import ACTION_AUTHORIZED, ACTION_EXECUTED, DECISION_PROPOSED
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.execution.executor_audit import (
    project_action_authorized_event,
    project_action_executed_event,
)
from runtime.platform.event_store.memory_event_store import MemoryEventStore
from runtime.state import (
    CanonicalBusinessEventStateProjector,
    build_canonical_state_synthesis_engine,
)
from storage.evidence_store import InMemoryEvidenceStore


@dataclass(frozen=True)
class _Decision:
    decision_id: str
    correlation_id: str
    action: str
    payload: dict[str, Any]
    issued_at_ms: int
    issuer_id: str = "phase5-test-sovereign"
    policy_id: str = "policy:phase5"
    snapshot_id: str = "snapshot:phase5"
    state_hash: str = "state-hash"


@dataclass(frozen=True)
class _Envelope:
    decision: _Decision
    payload_hash: str = "test-payload-hash"


class _SemanticDecisionIssuer:
    """Test issuer only; invocation still goes through the canonical gateway."""

    def __init__(self) -> None:
        self.calls = 0

    def issue(self, state):
        self.calls += 1
        semantic = getattr(state, "world_model_semantics", None)
        records = tuple(getattr(semantic, "records", ()) or ())
        has_verified_outcome = any(
            str(getattr(record, "value", {}).get("event_type") or "") == "outcome.observed"
            and bool(
                dict(getattr(record, "value", {}).get("payload") or {})
                .get("outcome", {})
                .get("verified")
            )
            for record in records
        )
        action = "notify_owner" if has_verified_outcome else "send_message"
        payload = attach_world_model_metadata(
            envelope_payload={
                "tenant_id": "tenant-phase5",
                "business_id": "business-phase5",
            },
            state=state,
        )
        return _Envelope(
            decision=_Decision(
                decision_id=f"decision-{self.calls}",
                correlation_id=f"correlation-{self.calls}",
                action=action,
                payload=payload,
                issued_at_ms=2_000 + self.calls,
            )
        )


def _request() -> GoalExecutionRequest:
    return GoalExecutionRequest(
        goal="Close the canonical feedback loop",
        tenant_id="tenant-phase5",
        business_id="business-phase5",
        max_steps=2,
    )


def _identity() -> ChannelIdentity:
    return ChannelIdentity(
        tenant_id="tenant-phase5",
        business_id="business-phase5",
        channel_kind=ChannelKind.API_BUSINESS,
        adapter_key="api.default",
        external_ref="external-phase5",
        region="global",
    )


def _allowed_execution_envelope(envelope, intent):
    policy = PolicyDecisionV1(
        tier="bounded_autonomy",
        action_type=intent.action_type,
        action_class="communications_write",
        allowed=True,
        approval_required=False,
        blocked_by_policy=False,
    ).bind_intent(intent)
    policy_payload = {**asdict(policy), "verdict": policy.verdict}
    payload = {
        **dict(envelope.decision.payload),
        "intent_id": intent.intent_id,
        "action_id": f"action:{intent.decision_id}",
        "action_channel": "headless",
        "evidence_refs": list(intent.evidence_refs),
        "derived_fact_ref": intent.derived_fact_ref,
        "capability_planning": {"allowed": True},
        "autonomy_safety": {
            "allowed": True,
            "operator_required": False,
            "reason": "within_bounds",
        },
        "policy_decision": policy_payload,
    }
    return replace(envelope, decision=replace(envelope.decision, payload=payload))


def test_phase5_real_fact_outcome_changes_world_model_and_next_canonical_decision(tmp_path) -> None:
    events = MemoryEventStore()
    evidence = InMemoryEvidenceStore()
    engine = build_canonical_state_synthesis_engine(root_dir=tmp_path)
    projector = CanonicalBusinessEventStateProjector(engine)

    initial = ExternalBusinessFactIngress(
        event_store=events,
        evidence_store=evidence,
        state_engine=engine,
        idempotency_store=InMemoryIdempotencyStore(),
    ).ingest(
        identity=_identity(),
        fact=NormalizedExternalBusinessFact(
            external_event_id="external-fact-1",
            fact_type="customer.reply.observed",
            entity_id="customer-1",
            payload={"reply": "interested"},
            occurred_at_ms=1_000,
            observed_at_ms=1_100,
            confidence=0.9,
        ),
        correlation_id="corr-external-phase5",
        recorded_at_ms=1_200,
    )

    mapper = HeadlessGoalStateMapper(semantic_snapshot_reader=engine.snapshot_store)
    request = _request()
    state_before = mapper.to_world_state(
        request=request,
        step_index=0,
        previous_feedback={},
    )
    assert state_before.world_model_semantics is not None
    assert state_before.world_model_semantics.state_id == initial.state_id

    issuer = _SemanticDecisionIssuer()
    first = issue_headless_decision(decision_core=issuer, state=state_before)
    assert first.decision.action == "send_message"

    intent = project_action_intent(
        decision_id=first.decision.decision_id,
        correlation_id=first.decision.correlation_id,
        decided_action_type=first.decision.action,
        channel="headless",
        tenant_id=request.tenant_id,
        business_id=request.business_id,
        payload=dict(first.decision.payload),
        requested_by=first.decision.issuer_id,
    )
    project_decision_proposed_event(
        event_store=events,
        envelope=first,
        action_intent=intent,
    )
    execution_envelope = _allowed_execution_envelope(first, intent)
    project_action_authorized_event(event_store=events, decision=execution_envelope.decision)
    project_action_executed_event(
        event_store=events,
        decision=execution_envelope.decision,
        verification={
            "verified": True,
            "status": "verified",
            "external_refs": ["provider:message:phase5"],
        },
        output={"status": "delivered"},
    )

    feedback = {
        "attempted": True,
        "executed": True,
        "verified": True,
        "verification_status": "verified",
        "evidence_status": "verified",
        "external_refs": ["provider:message:phase5"],
        "goal_evaluation": {
            "achieved": False,
            "terminal": False,
            "completion_ratio": 0.5,
            "success_confidence": 0.9,
        },
        "execution_feedback": {"source_of_truth": "provider_receipt"},
        "action_intent": intent.as_dict(),
    }
    feedback["business_outcome"] = BusinessOutcomeV1.from_feedback(
        tenant_id=request.tenant_id,
        business_id=request.business_id,
        run_id="run-phase5",
        intent_id=intent.intent_id,
        decision_id=intent.decision_id,
        action_id=f"action:{intent.decision_id}",
        action_type=intent.action_type,
        goal=request.goal,
        status="verified",
        feedback=feedback,
        evidence_refs=intent.evidence_refs,
        derived_fact_ref=intent.derived_fact_ref,
    ).as_dict()

    persistence = EvidencePersistenceService(
        evidence_store=evidence,
        event_store=events,
        world_model_event_projector=projector,
    )
    artifacts = persistence.persist_step_outcome(
        tenant_id=request.tenant_id,
        business_id=request.business_id,
        run_id="run-phase5",
        step_index=0,
        goal=request.goal,
        feedback=feedback,
        world_state_before=state_before,
    )
    assert artifacts is not None
    receipt = dict(artifacts.persistence_receipt or {})
    assert receipt["outcome_event_id"]
    assert receipt["canonical_evidence_id"]
    assert receipt["world_model_state_id"]
    assert receipt["world_model_state_id"] != initial.state_id

    replayed = persistence.persist(
        tenant_id=request.tenant_id,
        business_id=request.business_id,
        run_id="run-phase5",
        goal=request.goal,
        step_index=0,
        action={
            "action_type": intent.action_type,
            "action_id": f"action:{intent.decision_id}",
        },
        execution_result=feedback,
        verification_result=feedback,
        world_state_before={},
        world_state_after=None,
        final_feedback=feedback,
        step_count=1,
    )
    replay_receipt = dict(replayed.persistence_receipt or {})
    assert replay_receipt["canonical_evidence_id"] == receipt["canonical_evidence_id"]
    assert replay_receipt["outcome_event_id"] == receipt["outcome_event_id"]
    assert replay_receipt["world_model_state_id"] == receipt["world_model_state_id"]
    assert len(evidence.list_for_tenant(tenant_id=request.tenant_id)) == 2

    stale_snapshot = engine.snapshot_store.load_latest(
        tenant_id=request.tenant_id,
        business_id=request.business_id,
    )
    assert stale_snapshot is not None
    with pytest.raises(RuntimeError, match="STATE_SNAPSHOT_CONCURRENT_UPDATE"):
        engine.snapshot_store.save_snapshot_if_current(
            stale_snapshot,
            expected_state_id=initial.state_id,
        )

    state_after = mapper.to_world_state(
        request=request,
        step_index=1,
        previous_feedback=feedback,
    )
    assert state_after.world_model_semantics is not None
    assert state_after.world_model_semantics.state_id == receipt["world_model_state_id"]
    assert receipt["canonical_evidence_id"] in {
        evidence_id
        for record in state_after.world_model_semantics.records
        for evidence_id in record.evidence_refs
    }

    second = issue_headless_decision(decision_core=issuer, state=state_after)
    assert second.decision.action == "notify_owner"
    assert second.decision.action != first.decision.action
    assert (
        second.decision.payload["world_model_meta"]["semantic_state_id"]
        == receipt["world_model_state_id"]
    )
    assert (
        receipt["canonical_evidence_id"]
        in second.decision.payload["world_model_meta"]["evidence_refs"]
    )

    event_types = [
        str(event.get("event_type") or "")
        for event in events.iter_events(tenant_id=request.tenant_id, start_ms=0)
    ]
    assert DECISION_PROPOSED in event_types
    assert ACTION_AUTHORIZED in event_types
    assert ACTION_EXECUTED in event_types
    assert "outcome.observed" in event_types


def test_production_feedback_step_persists_outcome_before_next_step() -> None:
    from pathlib import Path

    source = Path("application/autonomy/autonomy_feedback_step.py").read_text(encoding="utf-8")
    outcome = source.index('feedback["business_outcome"] = BusinessOutcomeV1.from_feedback')
    persistence = source.index('"persist_step_outcome"', outcome)
    step_build = source.index("self._contract._step_builder.build(", persistence)
    assert outcome < persistence < step_build
