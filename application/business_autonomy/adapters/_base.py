from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from application.business_autonomy.channel_contracts import (
    ChannelCapabilityDescriptor,
    ChannelExecutionEnvelope,
    ChannelIdentity,
    ChannelKind,
)
from application.business_autonomy.contracts import (
    BusinessExecutionEvidence,
    BusinessExecutionRequest,
    BusinessExecutionResult,
    ExecutionVerdict,
)


@dataclass(frozen=True)
class StaticCapabilityBundle:
    descriptors: tuple[ChannelCapabilityDescriptor, ...]


class BaseStaticChannelAdapter:
    """Capability descriptor and simulation adapter, never a fake live transport.

    Subclasses that perform real writes must override ``execute`` and return
    provider evidence. The base preserves discovery and simulation UX, but a
    non-simulated call fails closed instead of claiming an external effect.
    """

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
        simulated = bool(request.envelope.simulation)
        verdict = ExecutionVerdict.SIMULATED if simulated else ExecutionVerdict.REJECTED
        reason = "simulation_completed" if simulated else "external_transport_not_configured"
        message = (
            f"{self.adapter_key} simulated the delegated execution envelope."
            if simulated
            else f"{self.adapter_key} has no live transport implementation; no external effect was performed."
        )
        evidence = (
            BusinessExecutionEvidence(
                event_type="channel_adapter_execution_proof",
                payload={
                    "adapter_key": self.adapter_key,
                    "operation": envelope.operation,
                    "external_effect": False,
                    "simulation": simulated,
                    "reason": reason,
                },
                timestamp_utc=datetime.now(UTC).isoformat(),
                source=self.adapter_key,
            ),
        )
        return BusinessExecutionResult(
            verdict=verdict,
            business_id=request.envelope.business_id,
            goal_id=request.envelope.goal_id,
            execution_id=request.correlation_id,
            message=message,
            metrics={
                "channel_kind": self.channel_kind.value,
                "adapter_key": self.adapter_key,
                "operation": envelope.operation,
                "external_effect": False,
            },
            evidence=evidence,
            delegated_to_domain_engine=True,
            adapter_name=self.adapter_key,
            metadata={
                "channel_kind": self.channel_kind.value,
                "adapter_key": self.adapter_key,
                "route_key": envelope.route_key,
                "external_ref": envelope.identity.external_ref,
                "region": envelope.identity.region,
                "transport_configured": False,
                "external_effect": False,
                "execution_reason": reason,
            },
        )
