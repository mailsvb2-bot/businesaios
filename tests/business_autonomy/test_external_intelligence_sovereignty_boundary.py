from __future__ import annotations

from dataclasses import dataclass

import pytest

from application.business_autonomy.channel_backed_adapter import ChannelBackedBusinessAdapter
from application.business_autonomy.channel_contracts import ChannelIdentity, ChannelKind
from application.business_autonomy.contracts import (
    BusinessCapability,
    BusinessExecutionRequest,
    BusinessExecutionResult,
    BusinessGoalEnvelope,
    CapabilityKind,
    ExecutionVerdict,
    IntegrationMode,
)
from application.business_autonomy.policy import AutonomyPolicyDecision
from application.business_autonomy.registry import BusinessAdapterRegistry
from application.business_autonomy.service import BusinessAutonomyService
from contracts.action_intent import ActionIntentV2


def _intent(*, business_id: str = "business-1", goal_id: str = "goal-1") -> ActionIntentV2:
    return ActionIntentV2.from_projection(
        action_id="action:decision-1",
        intent_id="intent:decision-1",
        tenant_id="tenant-1",
        business_id=business_id,
        decision_id="decision-1",
        correlation_id="corr-1",
        goal_id=goal_id,
        agent_id="agent-1",
        capability_target="send_message@v1",
        parameters={"recipient": "user-1", "text": "sovereign text"},
        payload_hash="a" * 64,
        channel="telegram",
    )


def _request(*, intent: ActionIntentV2 | None, mode: IntegrationMode = IntegrationMode.POLICY_GUARDED_DELEGATED):
    return BusinessExecutionRequest(
        envelope=BusinessGoalEnvelope(
            business_id="business-1",
            goal_id="goal-1",
            goal_type="reinterpret_this_goal",
            goal_payload={"text": "untrusted broad goal"},
        ),
        integration_mode=mode,
        correlation_id="corr-1",
        idempotency_key="idem-1",
        action_intent=intent,
    )


@dataclass
class _Policy:
    mode: IntegrationMode

    def choose_mode(self, request):
        return AutonomyPolicyDecision(True, self.mode, "test")


class _Adapter:
    business_id = "business-1"
    adapter_name = "external-ai"

    def __init__(self):
        self.legacy_calls = []
        self.intent_calls = []

    def supported_modes(self):
        return (
            IntegrationMode.POLICY_GUARDED_DELEGATED,
            IntegrationMode.DELEGATED_DOMAIN,
            IntegrationMode.SUPERVISED,
        )

    def declared_capabilities(self):
        return (BusinessCapability(kind=CapabilityKind.DOMAIN_AI),)

    async def execute(self, request):
        self.legacy_calls.append(request)
        return BusinessExecutionResult(
            verdict=ExecutionVerdict.COMPLETED,
            business_id=request.envelope.business_id,
            goal_id=request.envelope.goal_id,
            execution_id=request.correlation_id,
            message="legacy",
            adapter_name=self.adapter_name,
        )

    async def execute_intent(self, request):
        self.intent_calls.append(request)
        intent = request.action_intent
        return BusinessExecutionResult(
            verdict=ExecutionVerdict.COMPLETED,
            business_id=intent.business_id,
            goal_id=intent.goal_id,
            execution_id=request.correlation_id,
            message="intent",
            adapter_name=self.adapter_name,
        )


def _service(adapter, *, mode):
    registry = BusinessAdapterRegistry()
    registry.register(adapter)
    return BusinessAutonomyService(
        adapter_registry=registry,
        autonomy_policy=_Policy(mode),
    )


@pytest.mark.asyncio
async def test_managed_external_execution_fails_closed_without_action_intent():
    adapter = _Adapter()
    result = await _service(
        adapter, mode=IntegrationMode.POLICY_GUARDED_DELEGATED
    ).execute(_request(intent=None))
    assert result.verdict is ExecutionVerdict.REJECTED
    assert result.metadata["reason"] == "missing_action_intent"
    assert adapter.legacy_calls == []
    assert adapter.intent_calls == []


@pytest.mark.asyncio
async def test_managed_external_execution_uses_only_narrow_intent_surface():
    adapter = _Adapter()
    result = await _service(
        adapter, mode=IntegrationMode.POLICY_GUARDED_DELEGATED
    ).execute(_request(intent=_intent()))
    assert result.verdict is ExecutionVerdict.COMPLETED
    assert adapter.legacy_calls == []
    assert len(adapter.intent_calls) == 1
    external = adapter.intent_calls[0]
    assert external.action_intent.capability_target == "send_message@v1"
    assert external.action_intent.parameters_copy()["text"] == "sovereign text"
    assert not hasattr(external, "envelope")


@pytest.mark.asyncio
async def test_managed_external_execution_rejects_intent_scope_mismatch():
    adapter = _Adapter()
    result = await _service(
        adapter, mode=IntegrationMode.POLICY_GUARDED_DELEGATED
    ).execute(_request(intent=_intent(goal_id="other-goal")))
    assert result.verdict is ExecutionVerdict.REJECTED
    assert result.metadata["reason"] == "action_intent_scope_mismatch"
    assert adapter.legacy_calls == []
    assert adapter.intent_calls == []


@pytest.mark.asyncio
async def test_supervised_legacy_path_remains_compatible():
    adapter = _Adapter()
    result = await _service(
        adapter, mode=IntegrationMode.SUPERVISED
    ).execute(_request(intent=None, mode=IntegrationMode.SUPERVISED))
    assert result.verdict is ExecutionVerdict.COMPLETED
    assert len(adapter.legacy_calls) == 1
    assert adapter.intent_calls == []


class _Channel:
    channel_kind = ChannelKind.CHATBOT
    adapter_key = "telegram.test"

    def __init__(self):
        self.calls = []

    def discover_capabilities(self, *, identity):
        return ()

    async def execute(self, *, envelope, request):
        self.calls.append((envelope, request))
        return BusinessExecutionResult(
            verdict=ExecutionVerdict.COMPLETED,
            business_id=request.envelope.business_id,
            goal_id=request.envelope.goal_id,
            execution_id=request.correlation_id,
            message="channel",
            adapter_name=self.adapter_key,
        )


@pytest.mark.asyncio
async def test_channel_managed_projection_comes_from_action_intent_not_original_goal():
    channel = _Channel()
    adapter = ChannelBackedBusinessAdapter(
        identity=ChannelIdentity(
            business_id="business-1",
            tenant_id="tenant-1",
            channel_kind=ChannelKind.CHATBOT,
            adapter_key="telegram.test",
            external_ref="telegram.test",
        ),
        channel_adapter=channel,
        capabilities=(BusinessCapability(kind=CapabilityKind.DOMAIN_AI),),
    )
    result = await _service(
        adapter, mode=IntegrationMode.POLICY_GUARDED_DELEGATED
    ).execute(_request(intent=_intent()))
    assert result.verdict is ExecutionVerdict.COMPLETED
    envelope, projected_request = channel.calls[0]
    assert envelope.operation == "send_message@v1"
    assert envelope.payload == {"recipient": "user-1", "text": "sovereign text"}
    assert "untrusted broad goal" not in str(envelope.payload)
    assert projected_request.envelope.goal_type == "send_message@v1"
    assert projected_request.envelope.goal_payload["text"] == "sovereign text"
    assert projected_request.action_intent is not None
