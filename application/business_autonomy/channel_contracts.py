from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Protocol, Sequence

from application.business_autonomy.contracts import BusinessExecutionRequest, BusinessExecutionResult


class ChannelKind(str, Enum):
    CHATBOT = "chatbot"
    WEBSITE = "website"
    API_BUSINESS = "api_business"
    COMMERCE = "commerce"
    BACKOFFICE = "backoffice"
    CAMPAIGN_ADS = "campaign_ads"


@dataclass(frozen=True)
class ChannelIdentity:
    business_id: str
    tenant_id: str
    channel_kind: ChannelKind
    adapter_key: str
    external_ref: str
    region: str = "global"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not str(self.business_id or "").strip():
            raise ValueError("business_id is required")
        if not str(self.tenant_id or "").strip():
            raise ValueError("tenant_id is required")
        if not str(self.adapter_key or "").strip():
            raise ValueError("adapter_key is required")
        if not str(self.external_ref or "").strip():
            raise ValueError("external_ref is required")
        if not str(self.region or "").strip():
            raise ValueError("region is required")


@dataclass(frozen=True)
class ChannelCapabilityDescriptor:
    capability_key: str
    action_types: tuple[str, ...]
    write_enabled: bool = False
    human_verification_required: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not str(self.capability_key or "").strip():
            raise ValueError("capability_key is required")
        if not tuple(str(item).strip() for item in self.action_types if str(item).strip()):
            raise ValueError("action_types must not be empty")


@dataclass(frozen=True)
class ChannelExecutionEnvelope:
    identity: ChannelIdentity
    route_key: str
    operation: str
    payload: Mapping[str, Any]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        self.identity.validate()
        if not str(self.route_key or "").strip():
            raise ValueError("route_key is required")
        if not str(self.operation or "").strip():
            raise ValueError("operation is required")


class TypedChannelAdapter(Protocol):
    @property
    def channel_kind(self) -> ChannelKind: ...

    @property
    def adapter_key(self) -> str: ...

    def discover_capabilities(self, *, identity: ChannelIdentity) -> Sequence[ChannelCapabilityDescriptor]: ...

    async def execute(self, *, envelope: ChannelExecutionEnvelope, request: BusinessExecutionRequest) -> BusinessExecutionResult: ...


__all__ = [
    "ChannelCapabilityDescriptor",
    "ChannelExecutionEnvelope",
    "ChannelIdentity",
    "ChannelKind",
    "TypedChannelAdapter",
]
