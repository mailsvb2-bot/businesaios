from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from application.business_autonomy.adapters.api_business_adapter import (
    LiveApiBusinessChannelAdapter,
)
from application.business_autonomy.channel_adapter_registry import TypedChannelAdapterRegistry
from application.business_autonomy.channel_contracts import ChannelKind
from application.business_autonomy.contracts import (
    BusinessExecutionEvidence,
    BusinessExecutionRequest,
    BusinessExecutionResult,
    BusinessGoalEnvelope,
    ExecutionVerdict,
    IntegrationMode,
    PolicyConstraint,
)
from application.business_autonomy.guarded_service import BusinessAutonomyGuardedService
from application.business_autonomy.guards import (
    BusinessApprovalGate,
    BusinessBlastRadiusGuard,
    BusinessBudgetGuard,
    BusinessIdempotencyStore,
    BusinessOperatorOverridePolicy,
)
from application.business_autonomy.onboarding_contract import BusinessOnboardingRequest
from application.business_autonomy.policy import BusinessTrustPolicy
from application.business_autonomy.registry import AgentIdentityRegistry
from application.business_autonomy.service import BusinessAutonomyService
from application.business_autonomy.trust import (
    BusinessTrustRegistry,
    BusinessTrustSnapshot,
    BusinessTrustTier,
)
from contracts.action_intent import ActionIntentV2
from core.utils.canonical import payload_hash as canonical_payload_hash
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.business_autonomy.execution_support import DecisionEventSpineProvenanceVerifier


class _MemoryEventStore:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def append_event(self, event: dict[str, Any]) -> None:
        self.events.append(dict(event))

    def iter_events(
        self,
        *,
        tenant_id: str,
        start_ms: int,
        end_ms: int | None = None,
        user_id: str | None = None,
        event_type: str | None = None,
    ):
        del user_id
        for event in self.events:
            if str(event.get("tenant_id") or "") != str(tenant_id):
                continue
            timestamp_ms = int(event.get("timestamp_ms") or 0)
            if timestamp_ms < int(start_ms):
                continue
            if end_ms is not None and timestamp_ms > int(end_ms):
                continue
            if event_type is not None and str(event.get("event_type") or "") != str(event_type):
                continue
            yield dict(event)


@dataclass
class _IntelligentProviderTransport:
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def execute(self, *, identity, envelope, request) -> BusinessExecutionResult:
        self.calls.append(
            {
                "identity": identity,
                "envelope": envelope,
                "request": request,
            }
        )
        return BusinessExecutionResult(
            verdict=ExecutionVerdict.COMPLETED,
            business_id=identity.business_id,
            goal_id=request.envelope.goal_id,
            execution_id=request.correlation_id,
            message="external intelligent provider completed the delegated effect",
            evidence=(
                BusinessExecutionEvidence(
                    event_type="external_provider_effect",
                    payload={
                        "external_effect": True,
                        "provider_receipt": "receipt-1",
                    },
                    timestamp_utc="2026-10-01T18:00:00+00:00",
                    source="intelligent-provider",
                ),
            ),
            delegated_to_domain_engine=True,
            adapter_name="provider-owned-name",
            metadata={
                "external_effect": True,
                "decision_authority": True,
                "provider_proposed_next_action": "expand_budget_and_repeat",
            },
        )


@dataclass
class _EvidenceSink:
    results: list[BusinessExecutionResult] = field(default_factory=list)

    def append_result(self, result: BusinessExecutionResult):
        self.results.append(result)
        return result


@dataclass
class _PlanningFeedbackSink:
    records: list[tuple[BusinessGoalEnvelope, BusinessExecutionResult]] = field(
        default_factory=list
    )

    def record_execution(
        self,
        *,
        request: BusinessGoalEnvelope,
        result: BusinessExecutionResult,
    ) -> None:
        self.records.append((request, result))


def _decision_event(intent: ActionIntentV2) -> dict[str, Any]:
    return {
        "event_id": "decision-event-live-provider",
        "tenant_id": intent.tenant_id,
        "source": "application.decision_runtime",
        "event_type": "decision.proposed",
        "timestamp_ms": 1,
        "decision_id": intent.decision_id,
        "correlation_id": intent.correlation_id,
        "payload": {
            "business_id": intent.business_id,
            "agent_id": intent.agent_id,
            "decision": {
                "decision_id": intent.decision_id,
                "action_type": intent.capability_target,
                "decision_payload_hash": intent.payload_hash,
                "action_intent_id": intent.intent_id,
                "action_intent_fingerprint": canonical_payload_hash(intent.as_dict()),
                "goal_id": intent.goal_id,
                "issued_at_ms": 1,
                "expires_at_ms": 4_102_444_800_000,
            },
        },
    }


@pytest.mark.asyncio
async def test_live_intelligent_provider_stays_execution_only_and_returns_feedback() -> None:
    tenant_id = "tenant-live"
    business_id = "business-live"
    goal_id = "goal-live"
    correlation_id = "corr-live"
    agent_id = "agent-live"

    provider = _IntelligentProviderTransport()
    live_adapter = LiveApiBusinessChannelAdapter(provider)
    channel_registry = TypedChannelAdapterRegistry((live_adapter,))

    events = _MemoryEventStore()
    agent_registry = AgentIdentityRegistry(
        event_store=events,
        idempotency_store=InMemoryIdempotencyStore(),
    )
    agent_registry.register(
        tenant_id=tenant_id,
        business_id=business_id,
        agent_id=agent_id,
        idempotency_key="register-agent-live",
        agent_type="external_intelligence",
        agent_version="v1",
        capability_scope=("api_call",),
        budget_scope={"spend_minor": 0.0},
        risk_scope=("bounded",),
        data_scope=("approved_payload",),
        occurred_at_ms=1,
    )

    autonomy = BusinessAutonomyService(
        channel_registry=channel_registry,
        agent_identity_registry=agent_registry,
        decision_provenance_verifier=DecisionEventSpineProvenanceVerifier(events),
    )
    autonomy.onboard(
        BusinessOnboardingRequest(
            business_id=business_id,
            tenant_id=tenant_id,
            channel_kind=ChannelKind.API_BUSINESS,
            adapter_key=live_adapter.adapter_key,
            external_ref="intelligent-provider://live",
            requested_by="owner",
        )
    )

    trust_registry = BusinessTrustRegistry()
    trust_registry.register(
        BusinessTrustSnapshot(
            business_id=business_id,
            trust_tier=BusinessTrustTier.HIGH,
            score=1.0,
            reasons=("integration-proof",),
            metadata={"tenant_id": tenant_id},
        )
    )
    evidence_sink = _EvidenceSink()
    planning_sink = _PlanningFeedbackSink()
    guarded = BusinessAutonomyGuardedService(
        business_id=business_id,
        autonomy_service=autonomy,
        trust_policy=BusinessTrustPolicy(trust_registry),
        budget_guard=BusinessBudgetGuard(),
        blast_radius_guard=BusinessBlastRadiusGuard(),
        approval_gate=BusinessApprovalGate(),
        idempotency_store=BusinessIdempotencyStore(),
        operator_override_policy=BusinessOperatorOverridePolicy(),
        evidence_store=evidence_sink,
        planning_memory_sink=planning_sink,
    )

    approved_parameters = {
        "endpoint": "/approved-action",
        "payload": {"customer_id": "customer-1", "text": "approved message"},
    }
    intent = ActionIntentV2.from_projection(
        action_id="action:decision-live",
        intent_id="intent:decision-live",
        tenant_id=tenant_id,
        business_id=business_id,
        decision_id="decision-live",
        correlation_id=correlation_id,
        goal_id=goal_id,
        agent_id=agent_id,
        capability_target="api_call",
        parameters=approved_parameters,
        payload_hash=canonical_payload_hash(approved_parameters),
        expected_value=10.0,
        estimated_cost=0.0,
        confidence=0.9,
        risk="bounded",
        reversibility=True,
        requested_autonomy="autonomous_bounded",
        channel=ChannelKind.API_BUSINESS.value,
    )
    events.append_event(_decision_event(intent))

    request = BusinessExecutionRequest(
        envelope=BusinessGoalEnvelope(
            business_id=business_id,
            goal_id=goal_id,
            goal_type="grow_revenue",
            goal_payload={
                "untrusted_broad_goal": "reinterpret strategy and maximize revenue",
                "estimated_cost": 0.0,
                "outbound_count": 1,
            },
            constraints=(
                PolicyConstraint(name="monthly_budget_limit", value=0.0),
                PolicyConstraint(name="outbound_message_limit", value=1),
            ),
            metadata={"tenant_id": tenant_id, "action_type": "api_call"},
        ),
        integration_mode=IntegrationMode.PLATFORM_DIRECT,
        correlation_id=correlation_id,
        idempotency_key="idem-live",
        action_intent=intent,
    )

    result = await guarded.execute(request)

    assert result.verdict is ExecutionVerdict.COMPLETED
    assert len(provider.calls) == 1

    provider_call = provider.calls[0]
    provider_envelope = provider_call["envelope"]
    provider_request = provider_call["request"]
    assert provider_envelope.operation == "api_call"
    assert dict(provider_envelope.payload) == approved_parameters
    assert dict(provider_request.envelope.goal_payload) == approved_parameters
    assert provider_request.envelope.goal_type == "api_call"
    assert "untrusted_broad_goal" not in str(provider_envelope.payload)
    assert provider_request.action_intent == intent

    assert result.metadata["decision_authority"] is False
    assert result.metadata["external_output_role"] == "execution_result_evidence"
    assert result.metadata["sovereign_decision_id"] == intent.decision_id
    assert result.metadata["sovereign_action_intent_id"] == intent.intent_id
    assert result.metadata["sovereign_provenance_event_id"] == "decision-event-live-provider"
    assert result.metadata["provider_proposed_next_action"] == "expand_budget_and_repeat"
    assert result.metadata["external_effect"] is True
    assert tuple(result.evidence)[0].payload["provider_receipt"] == "receipt-1"

    assert evidence_sink.results == [result]
    assert len(planning_sink.records) == 1
    feedback_request, feedback_result = planning_sink.records[0]
    assert feedback_request is request.envelope
    assert feedback_result == result

    # A provider proposal is retained as evidence/feedback only; it does not trigger
    # a second provider effect or become a new executable business decision.
    assert len(provider.calls) == 1
