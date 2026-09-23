from __future__ import annotations

from dataclasses import replace
from typing import Protocol

from application.business_autonomy.adapters._base import BaseStaticChannelAdapter, StaticCapabilityBundle
from application.business_autonomy.channel_contracts import (
    ChannelCapabilityDescriptor,
    ChannelExecutionEnvelope,
    ChannelIdentity,
    ChannelKind,
)
from application.business_autonomy.contracts import (
    BusinessExecutionRequest,
    BusinessExecutionResult,
    ExecutionVerdict,
)


class ApiBusinessTransport(Protocol):
    """Injected live transport for an external business system.

    The transport owns protocol/provider details only. Business identity,
    governance and capability semantics stay in BusinessAIOS.
    """

    async def execute(
        self,
        *,
        identity: ChannelIdentity,
        envelope: ChannelExecutionEnvelope,
        request: BusinessExecutionRequest,
    ) -> BusinessExecutionResult: ...


class ApiBusinessChannelAdapter(BaseStaticChannelAdapter):
    """Discovery/simulation adapter.

    api.default deliberately does not advertise live write support. A
    configured live transport must use LiveApiBusinessChannelAdapter so
    capability discovery cannot claim an external side effect that the runtime
    cannot actually perform.
    """

    channel_kind = ChannelKind.API_BUSINESS
    adapter_key = "api.default"
    _capability_bundle = StaticCapabilityBundle(
        descriptors=(
            ChannelCapabilityDescriptor(
                "api.invoke",
                ("api_call",),
                write_enabled=False,
                human_verification_required=True,
            ),
            ChannelCapabilityDescriptor(
                "api.read_model",
                ("api_read",),
                write_enabled=False,
                human_verification_required=False,
            ),
        ),
    )


class LiveApiBusinessChannelAdapter(ApiBusinessChannelAdapter):
    """Provider-neutral live API-business adapter backed by an injected transport."""

    adapter_key = "api.live"
    _capability_bundle = StaticCapabilityBundle(
        descriptors=(
            ChannelCapabilityDescriptor(
                "api.invoke",
                ("api_call",),
                write_enabled=True,
                human_verification_required=True,
            ),
            ChannelCapabilityDescriptor(
                "api.read_model",
                ("api_read",),
                write_enabled=False,
                human_verification_required=False,
            ),
        ),
    )

    def __init__(self, transport: ApiBusinessTransport) -> None:
        if transport is None:
            raise ValueError("api business live transport is required")
        self._transport = transport

    async def execute(
        self,
        *,
        envelope: ChannelExecutionEnvelope,
        request: BusinessExecutionRequest,
    ) -> BusinessExecutionResult:
        envelope.validate()
        if str(request.envelope.business_id) != str(envelope.identity.business_id):
            raise ValueError("api business request/envelope business scope mismatch")

        if bool(request.envelope.simulation):
            return await super().execute(envelope=envelope, request=request)

        result = await self._transport.execute(
            identity=envelope.identity,
            envelope=envelope,
            request=request,
        )
        if str(result.business_id) != str(envelope.identity.business_id):
            raise RuntimeError("API_BUSINESS_TRANSPORT_SCOPE_MISMATCH")
        if str(result.goal_id) != str(request.envelope.goal_id):
            raise RuntimeError("API_BUSINESS_TRANSPORT_GOAL_MISMATCH")

        if str(envelope.operation) == "api_call":
            if result.verdict not in {
                ExecutionVerdict.ACCEPTED,
                ExecutionVerdict.COMPLETED,
                ExecutionVerdict.PARTIAL,
            }:
                raise RuntimeError("API_BUSINESS_WRITE_NOT_CONFIRMED")
            if not bool(dict(result.metadata or {}).get("external_effect")):
                raise RuntimeError("API_BUSINESS_WRITE_EVIDENCE_REQUIRED")
            if not tuple(result.evidence or ()):
                raise RuntimeError("API_BUSINESS_WRITE_EVIDENCE_REQUIRED")

        return replace(
            result,
            adapter_name=self.adapter_key,
            metadata={
                **dict(result.metadata or {}),
                "channel_kind": self.channel_kind.value,
                "adapter_key": self.adapter_key,
                "route_key": envelope.route_key,
                "external_ref": envelope.identity.external_ref,
                "region": envelope.identity.region,
                "transport_configured": True,
            },
        )


__all__ = [
    "ApiBusinessChannelAdapter",
    "ApiBusinessTransport",
    "LiveApiBusinessChannelAdapter",
]
