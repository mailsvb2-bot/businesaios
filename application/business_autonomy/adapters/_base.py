from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from application.business_autonomy.channel_contracts import (
    ChannelCapabilityDescriptor,
    ChannelExecutionEnvelope,
    ChannelIdentity,
    ChannelKind,
)
from application.business_autonomy.contracts import BusinessExecutionRequest, BusinessExecutionResult, ExecutionVerdict


@dataclass(frozen=True)
class StaticCapabilityBundle:
    descriptors: tuple[ChannelCapabilityDescriptor, ...]


class BaseStaticChannelAdapter:
    channel_kind: ChannelKind
    adapter_key: str
    _capability_bundle: StaticCapabilityBundle

    def discover_capabilities(self, *, identity: ChannelIdentity) -> Sequence[ChannelCapabilityDescriptor]:
        identity.validate()
        for item in self._capability_bundle.descriptors:
            item.validate()
        return self._capability_bundle.descriptors

    async def execute(self, *, envelope: ChannelExecutionEnvelope, request: BusinessExecutionRequest) -> BusinessExecutionResult:
        envelope.validate()
        verdict = ExecutionVerdict.SIMULATED if request.envelope.simulation else ExecutionVerdict.COMPLETED
        return BusinessExecutionResult(
            verdict=verdict,
            business_id=request.envelope.business_id,
            goal_id=request.envelope.goal_id,
            execution_id=request.correlation_id,
            message=f"{self.adapter_key} accepted delegated execution envelope.",
            metrics={
                "channel_kind": self.channel_kind.value,
                "adapter_key": self.adapter_key,
                "operation": envelope.operation,
            },
            evidence=(),
            delegated_to_domain_engine=True,
            adapter_name=self.adapter_key,
            metadata={
                "channel_kind": self.channel_kind.value,
                "adapter_key": self.adapter_key,
                "route_key": envelope.route_key,
                "external_ref": envelope.identity.external_ref,
                "region": envelope.identity.region,
            },
        )
