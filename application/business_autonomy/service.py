from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from application.business_autonomy.channel_adapter_registry import TypedChannelAdapterRegistry
from application.business_autonomy.channel_backed_adapter import ChannelBackedBusinessAdapter
from application.business_autonomy.channel_contracts import ChannelIdentity, ChannelKind
from application.business_autonomy.contracts import (
    BusinessCapability,
    BusinessExecutionRequest,
    BusinessExecutionResult,
    CapabilityKind,
    ExecutionVerdict,
)
from application.business_autonomy.guards import BusinessBlastRadiusGuard, BusinessBudgetGuard
from application.business_autonomy.non_ai_onboarding_mode import NonAiOperatingMode
from application.business_autonomy.onboarding_contract import BusinessOnboardingRequest
from application.business_autonomy.policy import BusinessAutonomyPolicy
from application.business_autonomy.registry import (
    BusinessAdapterRegistry,
    BusinessCapabilityRegistry,
    RegisteredBusinessCapabilities,
)


@dataclass(frozen=True)
class BusinessAutonomyOnboardingResult:
    business_id: str
    tenant_id: str
    adapter_name: str
    operating_mode: str
    guard_decisions: Mapping[str, Mapping[str, Any]]


class BusinessAutonomyService:
    def __init__(
        self,
        *,
        adapter_registry: BusinessAdapterRegistry | None = None,
        autonomy_policy: BusinessAutonomyPolicy | None = None,
        audit_sink: Optional[object] = None,
        channel_registry: TypedChannelAdapterRegistry | None = None,
        blast_radius_guard: BusinessBlastRadiusGuard | None = None,
        budget_guard: BusinessBudgetGuard | None = None,
    ) -> None:
        self._adapter_registry = adapter_registry or BusinessAdapterRegistry()
        self._capability_registry = BusinessCapabilityRegistry()
        self._autonomy_policy = autonomy_policy or BusinessAutonomyPolicy(self._capability_registry)
        self._audit_sink = audit_sink
        self._channel_registry = channel_registry or TypedChannelAdapterRegistry()
        self._blast_radius_guard = blast_radius_guard or BusinessBlastRadiusGuard()
        self._budget_guard = budget_guard or BusinessBudgetGuard()

    def onboard(self, request: BusinessOnboardingRequest) -> BusinessAutonomyOnboardingResult:
        identity = _identity_from_onboarding_request(request)
        resolved = self._channel_registry.resolve(identity)
        adapter = ChannelBackedBusinessAdapter(
            identity=identity,
            channel_adapter=resolved.adapter,
            capabilities=_capabilities_from_request(request),
        )
        self._adapter_registry.register(adapter)
        self._capability_registry.register(identity.business_id, adapter.declared_capabilities())
        blast_allowed = _metadata_int(request, 'parallel_actions', default=1) <= int(self._blast_radius_guard.max_parallel_actions or 1_000_000)
        requested_budget = _metadata_int(request, 'requested_budget_minor', default=0)
        budget_limit = self._budget_guard.max_budget_minor
        budget_allowed = budget_limit is None or requested_budget <= int(budget_limit)
        return BusinessAutonomyOnboardingResult(
            business_id=identity.business_id,
            tenant_id=identity.tenant_id,
            adapter_name=adapter.adapter_name,
            operating_mode=_operating_mode_from_request(request),
            guard_decisions={'blast_radius': {'allowed': blast_allowed}, 'budget': {'allowed': budget_allowed}},
        )

    def registered_adapter(self, business_id: str):
        return self._adapter_registry.get(business_id)

    def registered_capabilities(self, business_id: str) -> RegisteredBusinessCapabilities:
        return self._capability_registry.get(business_id)

    async def execute(self, request: BusinessExecutionRequest) -> BusinessExecutionResult:
        decision = self._autonomy_policy.choose_mode(request)
        if not decision.allowed:
            return BusinessExecutionResult(
                verdict=ExecutionVerdict.REJECTED,
                business_id=request.envelope.business_id,
                goal_id=request.envelope.goal_id,
                execution_id=request.correlation_id,
                message=decision.reason,
                delegated_to_domain_engine=False,
                adapter_name=None,
                metadata={"policy_reason": decision.reason},
            )
        adapter = self._adapter_registry.get(request.envelope.business_id)
        delegated_request = BusinessExecutionRequest(
            envelope=request.envelope,
            integration_mode=decision.mode,
            correlation_id=request.correlation_id,
            idempotency_key=request.idempotency_key,
            timeout_seconds=request.timeout_seconds,
        )
        supported_modes = tuple(adapter.supported_modes())
        if delegated_request.integration_mode not in supported_modes:
            return BusinessExecutionResult(
                verdict=ExecutionVerdict.REJECTED,
                business_id=request.envelope.business_id,
                goal_id=request.envelope.goal_id,
                execution_id=request.correlation_id,
                message=f"Adapter does not support integration mode: {delegated_request.integration_mode.value}",
                delegated_to_domain_engine=False,
                adapter_name=adapter.adapter_name,
                metadata={"supported_modes": [item.value for item in supported_modes]},
            )
        result = await adapter.execute(delegated_request)
        if self._audit_sink is not None and hasattr(self._audit_sink, "record"):
            self._audit_sink.record(event_type="business_autonomy_result", business_id=result.business_id, goal_id=result.goal_id, detail={"verdict": result.verdict.value, "adapter_name": result.adapter_name})
        return result


def _identity_from_onboarding_request(request: BusinessOnboardingRequest) -> ChannelIdentity:
    to_identity = getattr(request, 'to_identity', None)
    try:
        if callable(to_identity):
            return to_identity()
    except (TypeError, ValueError):
        pass
    channel_kind = _coerce_channel_kind(getattr(request, 'channel_kind', 'chatbot'))
    adapter_key = str(getattr(request, 'adapter_key', '') or f"{_raw_channel_kind(getattr(request, 'channel_kind', channel_kind))}.default")
    return ChannelIdentity(
        business_id=str(getattr(request, 'business_id')),
        tenant_id=str(getattr(request, 'tenant_id')),
        channel_kind=channel_kind,
        adapter_key=adapter_key,
        external_ref=str(getattr(request, 'external_ref', '') or adapter_key),
        region=str(getattr(request, 'region', '') or 'global'),
        metadata=dict(getattr(request, 'metadata', {}) or {}),
    )


def _coerce_channel_kind(value: object) -> ChannelKind:
    if isinstance(value, ChannelKind):
        return value
    raw = _raw_channel_kind(value)
    aliases = {'telegram': ChannelKind.CHATBOT, 'webchat': ChannelKind.CHATBOT, 'chat': ChannelKind.CHATBOT}
    if raw in aliases:
        return aliases[raw]
    try:
        return ChannelKind(raw)
    except ValueError:
        return ChannelKind.CHATBOT


def _raw_channel_kind(value: object) -> str:
    if isinstance(value, ChannelKind):
        return value.value
    return str(value or 'chatbot').strip().lower().replace('-', '_')


def _capabilities_from_request(request: BusinessOnboardingRequest) -> tuple[BusinessCapability, ...]:
    requested = tuple(str(item).strip().lower() for item in getattr(request, 'requested_capabilities', ()) or ())
    if not requested:
        return (BusinessCapability(kind=CapabilityKind.DOMAIN_AI),)
    mapped: list[BusinessCapability] = []
    for item in requested:
        kind = CapabilityKind.ANALYTICS_ENGINE if item == 'analytics' else CapabilityKind.DOMAIN_AI
        mapped.append(BusinessCapability(kind=kind))
    return tuple(mapped)


def _operating_mode_from_request(request: BusinessOnboardingRequest) -> str:
    metadata = dict(getattr(request, 'metadata', {}) or {})
    raw = str(metadata.get('non_ai_mode') or getattr(request, 'integration_mode', '') or '').strip().lower()
    if raw in {'channel_driven', 'non_ai'}:
        return getattr(NonAiOperatingMode, 'CHANNEL_DRIVEN', NonAiOperatingMode.SUPERVISED).value
    try:
        return NonAiOperatingMode(raw).value
    except ValueError:
        return getattr(NonAiOperatingMode, 'CHANNEL_DRIVEN', NonAiOperatingMode.SUPERVISED).value


def _metadata_int(request: BusinessOnboardingRequest, key: str, *, default: int) -> int:
    try:
        return int((getattr(request, 'metadata', {}) or {}).get(key, default))
    except (TypeError, ValueError):
        return default


__all__ = ["BusinessAutonomyOnboardingResult", "BusinessAutonomyService"]
