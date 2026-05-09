from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from application.business_autonomy.channel_contracts import ChannelExecutionEnvelope, ChannelIdentity, ChannelKind, TypedChannelAdapter
from application.business_autonomy.contracts import (
    BusinessCapability,
    BusinessExecutionRequest,
    BusinessExecutionResult,
    CapabilityKind,
    ExecutionVerdict,
    IntegrationMode,
)
from application.business_autonomy.protocol import ExternalBusinessAdapter


class _CompatibilityTypedChannelAdapter:
    def __init__(self, *, adapter_key: str, channel_kind: ChannelKind) -> None:
        self._adapter_key = adapter_key
        self._channel_kind = channel_kind

    @property
    def channel_kind(self) -> ChannelKind:
        return self._channel_kind

    @property
    def adapter_key(self) -> str:
        return self._adapter_key

    def discover_capabilities(self, *, identity: ChannelIdentity):
        return ()

    async def execute(self, *, envelope: ChannelExecutionEnvelope, request: BusinessExecutionRequest) -> BusinessExecutionResult:
        return BusinessExecutionResult(
            verdict=ExecutionVerdict.COMPLETED,
            business_id=request.envelope.business_id,
            goal_id=request.envelope.goal_id,
            execution_id=request.correlation_id,
            message='channel-backed compatibility adapter executed',
            adapter_name=self.adapter_key,
            delegated_to_domain_engine=True,
            metadata={'channel_kind': self.channel_kind.value, 'route_key': envelope.route_key},
        )


@dataclass(frozen=True, init=False)
class ChannelBackedBusinessAdapter(ExternalBusinessAdapter):
    identity: ChannelIdentity
    channel_adapter: TypedChannelAdapter
    capabilities: tuple[BusinessCapability, ...]
    modes: tuple[IntegrationMode, ...]

    def __init__(
        self,
        identity: ChannelIdentity | None = None,
        channel_adapter: TypedChannelAdapter | None = None,
        capabilities: Sequence[BusinessCapability] | None = None,
        modes: Sequence[IntegrationMode] | None = None,
        *,
        adapter_name: str | None = None,
        channel_kind: str | ChannelKind | None = None,
        business_id: str = 'business-default',
        tenant_id: str = 'tenant-default',
    ) -> None:
        if identity is None:
            kind = _coerce_channel_kind(channel_kind)
            key = str(adapter_name or f'{kind.value}.default')
            identity = ChannelIdentity(
                business_id=str(business_id or 'business-default'),
                tenant_id=str(tenant_id or 'tenant-default'),
                channel_kind=kind,
                adapter_key=key,
                external_ref=key,
            )
        if channel_adapter is None:
            channel_adapter = _CompatibilityTypedChannelAdapter(adapter_key=identity.adapter_key, channel_kind=identity.channel_kind)
        if capabilities is None:
            capabilities = (BusinessCapability(kind=CapabilityKind.DOMAIN_AI),)
        if modes is None:
            modes = (
                IntegrationMode.PLATFORM_DIRECT,
                IntegrationMode.POLICY_GUARDED_DELEGATED,
                IntegrationMode.SUPERVISED,
                IntegrationMode.LOW_AUTONOMY,
            )
        object.__setattr__(self, 'identity', identity)
        object.__setattr__(self, 'channel_adapter', channel_adapter)
        object.__setattr__(self, 'capabilities', tuple(capabilities))
        object.__setattr__(self, 'modes', tuple(modes))

    @property
    def adapter_name(self) -> str:
        return self.channel_adapter.adapter_key

    @property
    def business_id(self) -> str:
        return self.identity.business_id

    def supported_modes(self) -> Sequence[IntegrationMode]:
        return self.modes

    def declared_capabilities(self) -> Sequence[BusinessCapability]:
        return self.capabilities

    async def execute(self, request: BusinessExecutionRequest) -> BusinessExecutionResult:
        envelope = ChannelExecutionEnvelope(
            identity=self.identity,
            route_key=f"{self.identity.tenant_id}:{self.identity.business_id}",
            operation=str(request.envelope.goal_type or 'execute'),
            payload=dict(request.envelope.goal_payload),
            metadata=dict(request.envelope.metadata),
        )
        return await self.channel_adapter.execute(envelope=envelope, request=request)


def _coerce_channel_kind(value: str | ChannelKind | None) -> ChannelKind:
    if isinstance(value, ChannelKind):
        return value
    raw = str(value or 'chatbot').strip().lower().replace('-', '_')
    aliases = {'telegram': ChannelKind.CHATBOT, 'webchat': ChannelKind.CHATBOT, 'chat': ChannelKind.CHATBOT}
    if raw in aliases:
        return aliases[raw]
    try:
        return ChannelKind(raw)
    except ValueError:
        return ChannelKind.CHATBOT
