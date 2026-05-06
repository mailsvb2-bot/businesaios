from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from application.business_autonomy.channel_contracts import ChannelExecutionEnvelope, ChannelIdentity, TypedChannelAdapter
from application.business_autonomy.contracts import BusinessCapability, BusinessExecutionRequest, BusinessExecutionResult, IntegrationMode
from application.business_autonomy.protocol import ExternalBusinessAdapter


@dataclass(frozen=True)
class ChannelBackedBusinessAdapter(ExternalBusinessAdapter):
    identity: ChannelIdentity
    channel_adapter: TypedChannelAdapter
    capabilities: tuple[BusinessCapability, ...]
    modes: tuple[IntegrationMode, ...]

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
