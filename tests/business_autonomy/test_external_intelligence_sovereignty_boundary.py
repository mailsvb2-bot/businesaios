from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

from application.business_autonomy.channel_backed_adapter import ChannelBackedBusinessAdapter
from application.business_autonomy.channel_contracts import ChannelIdentity, ChannelKind
from application.business_autonomy.contracts import (
    BusinessCapability,
    BusinessExecutionRequest,
    BusinessExecutionResult,
    BusinessGoalEnvelope,
    CapabilityKind,
    ExternalExecutionRequest,
    ExecutionVerdict,
    IntegrationMode,
)
from application.business_autonomy.decision_provenance import DecisionEventSpineProvenanceVerifier
from application.business_autonomy.execution_subject import business_execution_fingerprint
from application.business_autonomy.policy import AutonomyPolicyDecision
from application.business_autonomy.registry import BusinessAdapterRegistry
from application.business_autonomy.service import BusinessAutonomyService
from contracts.action_intent import ActionIntentV2
from core.utils.canonical import payload_hash as canonical_payload_hash



ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "application" / "business_autonomy" / "contracts.py"
SERVICE = ROOT / "application" / "business_autonomy" / "service.py"
PROVENANCE = ROOT / "application" / "business_autonomy" / "decision_provenance.py"
BOOTSTRAP = ROOT / "runtime" / "business_autonomy" / "bootstrap.py"
POLICY = ROOT / "application" / "business_autonomy" / "policy.py"


def _intent(
    *,
    business_id: str = "business-1",
    goal_id: str = "goal-1",
    correlation_id: str = "corr-1",
    payload_hash: str | None = None,
) -> ActionIntentV2:
    parameters = {"recipient": "user-1", "text": "sovereign text"}
    return ActionIntentV2.from_projection(
        action_id="action:decision-1",
        intent_id="intent:decision-1",
        tenant_id="tenant-1",
        business_id=business_id,
        decision_id="decision-1",
        correlation_id=correlation_id,
        goal_id=goal_id,
        agent_id="agent-1",
        capability_target="send_message@v1",
        parameters=parameters,
        payload_hash=payload_hash or canonical_payload_hash(parameters),
        channel="telegram",
    )


def _request(*, intent: ActionIntentV2 | None, mode: IntegrationMode = IntegrationMode.POLICY_GUARDED_DELEGATED):
    return BusinessExecutionRequest(
        envelope=BusinessGoalEnvelope(
            business_id="business-1",
            goal_id="goal-1",
            goal_type="reinterpret_this_goal",
            goal_payload={"text": "untrusted broad goal"},
            metadata={"tenant_id": "tenant-1"},
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


class _AgentRegistry:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.calls = []

    def assert_execution_authorized(self, **kwargs):
        self.calls.append(dict(kwargs))
        if self.error is not None:
            raise self.error
        return object()


class _ProvenanceVerifier:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.calls = []

    def assert_intent_provenance(self, intent):
        self.calls.append(intent)
        if self.error is not None:
            raise self.error
        return f"decision-event:{intent.decision_id}"


_DEFAULT_PROVENANCE = object()


def _service(adapter, *, mode, agent_registry=None, provenance_verifier=_DEFAULT_PROVENANCE):
    registry = BusinessAdapterRegistry()
    registry.register(adapter)
    if provenance_verifier is _DEFAULT_PROVENANCE:
        provenance_verifier = _ProvenanceVerifier()
    return BusinessAutonomyService(
        adapter_registry=registry,
        autonomy_policy=_Policy(mode),
        agent_identity_registry=agent_registry,
        decision_provenance_verifier=provenance_verifier,
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
    agent_registry = _AgentRegistry()
    result = await _service(
        adapter,
        mode=IntegrationMode.POLICY_GUARDED_DELEGATED,
        agent_registry=agent_registry,
    ).execute(_request(intent=_intent()))
    assert result.verdict is ExecutionVerdict.COMPLETED
    assert adapter.legacy_calls == []
    assert len(adapter.intent_calls) == 1
    assert agent_registry.calls == [{
        "tenant_id": "tenant-1",
        "business_id": "business-1",
        "agent_id": "agent-1",
        "capability": "send_message@v1",
    }]
    external = adapter.intent_calls[0]
    assert external.action_intent.capability_target == "send_message@v1"
    assert external.action_intent.parameters_copy()["text"] == "sovereign text"
    assert not hasattr(external, "envelope")


@pytest.mark.asyncio
async def test_managed_external_execution_rejects_intent_scope_mismatch():
    adapter = _Adapter()
    result = await _service(
        adapter,
        mode=IntegrationMode.POLICY_GUARDED_DELEGATED,
        agent_registry=_AgentRegistry(),
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
        adapter,
        mode=IntegrationMode.POLICY_GUARDED_DELEGATED,
        agent_registry=_AgentRegistry(),
    ).execute(_request(intent=_intent()))
    assert result.verdict is ExecutionVerdict.COMPLETED
    envelope, projected_request = channel.calls[0]
    assert envelope.operation == "send_message@v1"
    assert envelope.payload == {"recipient": "user-1", "text": "sovereign text"}
    assert "untrusted broad goal" not in str(envelope.payload)
    assert projected_request.envelope.goal_type == "send_message@v1"
    assert projected_request.envelope.goal_payload["text"] == "sovereign text"
    assert projected_request.action_intent is not None


@pytest.mark.asyncio
async def test_managed_external_execution_rejects_forged_payload_hash():
    adapter = _Adapter()
    result = await _service(
        adapter,
        mode=IntegrationMode.POLICY_GUARDED_DELEGATED,
        agent_registry=_AgentRegistry(),
    ).execute(_request(intent=_intent(payload_hash="f" * 64)))
    assert result.verdict is ExecutionVerdict.REJECTED
    assert result.metadata["reason"] == "action_intent_payload_hash_mismatch"
    assert adapter.intent_calls == []


@pytest.mark.asyncio
async def test_managed_external_execution_rejects_correlation_scope_mismatch():
    adapter = _Adapter()
    result = await _service(
        adapter,
        mode=IntegrationMode.POLICY_GUARDED_DELEGATED,
        agent_registry=_AgentRegistry(),
    ).execute(_request(intent=_intent(correlation_id="other-correlation")))
    assert result.verdict is ExecutionVerdict.REJECTED
    assert result.metadata["reason"] == "action_intent_scope_mismatch"
    assert adapter.intent_calls == []


@pytest.mark.asyncio
async def test_managed_external_execution_fails_closed_without_decision_provenance():
    adapter = _Adapter()
    result = await _service(
        adapter,
        mode=IntegrationMode.POLICY_GUARDED_DELEGATED,
        agent_registry=_AgentRegistry(),
        provenance_verifier=None,
    ).execute(_request(intent=_intent()))
    assert result.verdict is ExecutionVerdict.REJECTED
    assert result.metadata["reason"] == "missing_decision_provenance_verifier"
    assert adapter.intent_calls == []


@pytest.mark.asyncio
async def test_managed_external_execution_rejects_conflicting_decision_provenance():
    adapter = _Adapter()
    result = await _service(
        adapter,
        mode=IntegrationMode.POLICY_GUARDED_DELEGATED,
        agent_registry=_AgentRegistry(),
        provenance_verifier=_ProvenanceVerifier(ValueError("payload hash mismatch")),
    ).execute(_request(intent=_intent()))
    assert result.verdict is ExecutionVerdict.REJECTED
    assert result.metadata["reason"] == "decision_provenance_denied"
    assert result.metadata["failure_type"] == "ValueError"
    assert adapter.intent_calls == []


@pytest.mark.asyncio
async def test_managed_external_execution_rechecks_agent_authorization_before_adapter():
    adapter = _Adapter()
    registry = _AgentRegistry(PermissionError("agent delegation chain contains revoked identity"))
    result = await _service(
        adapter,
        mode=IntegrationMode.POLICY_GUARDED_DELEGATED,
        agent_registry=registry,
    ).execute(_request(intent=_intent()))
    assert result.verdict is ExecutionVerdict.REJECTED
    assert result.metadata["reason"] == "agent_authorization_denied"
    assert adapter.legacy_calls == []
    assert adapter.intent_calls == []


@pytest.mark.asyncio
async def test_managed_external_execution_fails_closed_without_agent_registry():
    adapter = _Adapter()
    result = await _service(
        adapter,
        mode=IntegrationMode.POLICY_GUARDED_DELEGATED,
        agent_registry=None,
    ).execute(_request(intent=_intent()))
    assert result.verdict is ExecutionVerdict.REJECTED
    assert result.metadata["reason"] == "missing_agent_identity_registry"
    assert adapter.legacy_calls == []
    assert adapter.intent_calls == []


class _DecisionClaimingAdapter(_Adapter):
    async def execute_intent(self, request):
        result = await super().execute_intent(request)
        return BusinessExecutionResult(
            verdict=result.verdict,
            business_id=result.business_id,
            goal_id=result.goal_id,
            execution_id=result.execution_id,
            message=result.message,
            adapter_name=result.adapter_name,
            metadata={
                "decision_authority": True,
                "next_action": "replace_business_strategy",
            },
        )


@pytest.mark.asyncio
async def test_managed_external_output_is_evidence_only_even_if_provider_claims_decision_authority():
    adapter = _DecisionClaimingAdapter()
    result = await _service(
        adapter,
        mode=IntegrationMode.POLICY_GUARDED_DELEGATED,
        agent_registry=_AgentRegistry(),
    ).execute(_request(intent=_intent()))
    assert result.verdict is ExecutionVerdict.COMPLETED
    assert result.metadata["decision_authority"] is False
    assert result.metadata["external_output_role"] == "execution_result_evidence"
    assert result.metadata["sovereign_decision_id"] == "decision-1"
    assert result.metadata["sovereign_action_intent_id"] == "intent:decision-1"
    assert result.metadata["next_action"] == "replace_business_strategy"


class _ScopeSpoofingAdapter(_Adapter):
    async def execute_intent(self, request):
        self.intent_calls.append(request)
        return BusinessExecutionResult(
            verdict=ExecutionVerdict.COMPLETED,
            business_id="other-business",
            goal_id="other-goal",
            execution_id="other-execution",
            message="spoofed",
            adapter_name=self.adapter_name,
        )


@pytest.mark.asyncio
async def test_managed_external_result_cannot_escape_sovereign_scope():
    adapter = _ScopeSpoofingAdapter()
    result = await _service(
        adapter,
        mode=IntegrationMode.POLICY_GUARDED_DELEGATED,
        agent_registry=_AgentRegistry(),
    ).execute(_request(intent=_intent()))
    assert result.verdict is ExecutionVerdict.REJECTED
    assert result.business_id == "business-1"
    assert result.goal_id == "goal-1"
    assert result.execution_id == "corr-1"
    assert result.metadata["reason"] == "external_result_scope_mismatch"


@pytest.mark.asyncio
async def test_managed_external_execution_rejects_tenant_scope_mismatch():
    adapter = _Adapter()
    intent = ActionIntentV2.from_projection(
        action_id="action:decision-tenant",
        intent_id="intent:decision-tenant",
        tenant_id="other-tenant",
        business_id="business-1",
        decision_id="decision-tenant",
        correlation_id="corr-1",
        goal_id="goal-1",
        agent_id="agent-1",
        capability_target="send_message@v1",
        parameters={"recipient": "user-1", "text": "sovereign text"},
        payload_hash=canonical_payload_hash({"recipient": "user-1", "text": "sovereign text"}),
        channel="telegram",
    )
    result = await _service(
        adapter,
        mode=IntegrationMode.POLICY_GUARDED_DELEGATED,
        agent_registry=_AgentRegistry(),
    ).execute(_request(intent=intent))
    assert result.verdict is ExecutionVerdict.REJECTED
    assert result.metadata["reason"] == "action_intent_scope_mismatch"
    assert adapter.intent_calls == []


class _DecisionEventStore:
    def __init__(self, events):
        self.events = list(events)

    def iter_events(self, *, tenant_id, start_ms, event_type):
        del start_ms
        return [
            event
            for event in self.events
            if event.get("tenant_id") == tenant_id
            and event.get("event_type") == event_type
        ]


def _decision_event_for_intent(intent: ActionIntentV2, **decision_patch):
    decision = {
        "decision_id": intent.decision_id,
        "action_type": intent.capability_target,
        "decision_payload_hash": intent.payload_hash,
        "action_intent_id": intent.intent_id,
        "action_intent_fingerprint": canonical_payload_hash(intent.as_dict()),
        "goal_id": intent.goal_id,
        "issued_at_ms": 1,
        "expires_at_ms": 4_102_444_800_000,
    }
    decision.update(decision_patch)
    return {
        "event_id": "event-1",
        "tenant_id": intent.tenant_id,
        "source": "application.decision_runtime",
        "event_type": "decision.proposed",
        "decision_id": intent.decision_id,
        "correlation_id": intent.correlation_id,
        "payload": {
            "business_id": intent.business_id,
            "agent_id": intent.agent_id,
            "decision": decision,
        },
    }


def test_decision_event_spine_provenance_binds_exact_sovereign_lineage():
    intent = _intent()
    verifier = DecisionEventSpineProvenanceVerifier(
        _DecisionEventStore([_decision_event_for_intent(intent)])
    )
    assert verifier.assert_intent_provenance(intent) == "event-1"


def test_decision_event_spine_provenance_rejects_payload_hash_drift():
    intent = _intent()
    event = _decision_event_for_intent(intent, decision_payload_hash="0" * 64)
    verifier = DecisionEventSpineProvenanceVerifier(_DecisionEventStore([event]))
    with pytest.raises(ValueError, match="decision_payload_hash"):
        verifier.assert_intent_provenance(intent)


def test_decision_event_spine_provenance_rejects_full_intent_semantic_drift():
    intent = _intent()
    event = _decision_event_for_intent(
        intent,
        action_intent_fingerprint="0" * 64,
    )
    verifier = DecisionEventSpineProvenanceVerifier(_DecisionEventStore([event]))
    with pytest.raises(ValueError, match="action_intent_fingerprint"):
        verifier.assert_intent_provenance(intent)


def test_decision_event_spine_provenance_rejects_expired_signed_decision():
    intent = _intent()
    event = _decision_event_for_intent(intent, expires_at_ms=2)
    verifier = DecisionEventSpineProvenanceVerifier(_DecisionEventStore([event]))
    with pytest.raises(ValueError, match="expired"):
        verifier.assert_intent_provenance(intent)


def test_execution_fingerprint_changes_when_sovereign_intent_changes():
    first = _request(intent=_intent())
    second_intent = ActionIntentV2.from_projection(
        action_id="action:decision-2",
        intent_id="intent:decision-2",
        tenant_id="tenant-1",
        business_id="business-1",
        decision_id="decision-2",
        correlation_id="corr-1",
        goal_id="goal-1",
        agent_id="agent-1",
        capability_target="send_message@v1",
        parameters={"recipient": "user-1", "text": "different sovereign text"},
        payload_hash=canonical_payload_hash(
            {"recipient": "user-1", "text": "different sovereign text"}
        ),
        channel="telegram",
    )
    second = _request(intent=second_intent)
    assert business_execution_fingerprint(first) != business_execution_fingerprint(second)


def test_managed_external_request_has_no_business_goal_envelope_field() -> None:
    fields = set(ExternalExecutionRequest.__dataclass_fields__)
    assert "action_intent" in fields
    assert "envelope" not in fields
    assert "goal" not in fields
    assert "goal_payload" not in fields


def test_managed_service_never_falls_back_to_goal_level_execute() -> None:
    tree = ast.parse(SERVICE.read_text(encoding="utf-8"), filename=str(SERVICE))
    source = SERVICE.read_text(encoding="utf-8")
    assert "managed_intent_boundary_unsupported" in source
    assert "missing_action_intent" in source
    managed_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "execute_intent"
    ]
    assert managed_calls


def test_external_execution_contract_owner_reuses_action_intent_v2() -> None:
    tree = ast.parse(CONTRACTS.read_text(encoding="utf-8"), filename=str(CONTRACTS))
    external = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "ExternalExecutionRequest"
    )
    annotations = {
        node.target.id: ast.unparse(node.annotation)
        for node in external.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    assert annotations["action_intent"] == "ActionIntentV2"



def test_managed_boundary_revalidates_intent_integrity_before_external_effect() -> None:
    source = SERVICE.read_text(encoding="utf-8")
    assert "canonical_payload_hash(intent.parameters_copy()) != intent.payload_hash" in source
    assert "intent.correlation_id != delegated_request.correlation_id" in source


def test_managed_external_outputs_are_explicitly_non_authoritative() -> None:
    source = SERVICE.read_text(encoding="utf-8")
    assert '"external_output_role": "execution_result_evidence"' in source
    assert '"decision_authority": False' in source



def test_managed_provenance_reuses_event_spine_without_second_crypto_verifier() -> None:
    source = PROVENANCE.read_text(encoding="utf-8")
    assert "DECISION_PROPOSED" in source
    assert "decision_payload_hash" in source
    assert "action_intent_id" in source
    assert "decision_crypto" not in source
    assert "verify_signed_material" not in source
    assert "signature_gate" not in source


def test_production_business_autonomy_wires_canonical_decision_provenance() -> None:
    source = BOOTSTRAP.read_text(encoding="utf-8")
    support = (ROOT / "runtime" / "business_autonomy" / "execution_support.py").read_text(
        encoding="utf-8"
    )
    assert "build_decision_provenance_verifier" in source
    assert "event_store=ontology_event_store" in source
    assert "decision_provenance_verifier=" in source
    assert "DecisionEventSpineProvenanceVerifier" in support

def test_intelligent_domain_owners_are_forced_through_managed_mode() -> None:
    source = POLICY.read_text(encoding="utf-8")
    for capability in ("CapabilityKind.DOMAIN_AI", "CapabilityKind.DOMAIN_PLANNER", "CapabilityKind.DOMAIN_SCHEDULER"):
        assert capability in source
    domain_branch = source.index("if has_domain_owner:")
    managed_mode = source.index("IntegrationMode.POLICY_GUARDED_DELEGATED", domain_branch)
    low_autonomy = source.index("IntegrationMode.LOW_AUTONOMY", managed_mode)
    supervised = source.index("IntegrationMode.SUPERVISED", low_autonomy)
    assert domain_branch < managed_mode < low_autonomy < supervised


def test_managed_provenance_binds_full_intent_and_signed_lifetime() -> None:
    provenance = PROVENANCE.read_text(encoding="utf-8")
    emission = (ROOT / "application" / "decision_runtime" / "emission.py").read_text(encoding="utf-8")
    assert "action_intent_fingerprint" in emission
    assert "expires_at_ms" in emission
    assert "action_intent_fingerprint" in provenance
    assert "canonical decision provenance is expired" in provenance

