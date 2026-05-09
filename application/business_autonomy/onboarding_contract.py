from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from core.tenancy.normalization import require_tenant_id
from application.business_autonomy.channel_contracts import ChannelIdentity, ChannelKind


class OnboardingStage(str, Enum):
    REGISTERED = "registered"
    CAPABILITY_DISCOVERED = "capability_discovered"
    TRUST_ONBOARDED = "trust_onboarded"
    MODE_RESOLVED = "mode_resolved"
    OWNERSHIP_BOUND = "ownership_bound"
    GOVERNANCE_ENABLED = "governance_enabled"
    PERSISTENCE_ENABLED = "persistence_enabled"
    READY = "ready"


@dataclass(frozen=True)
class BusinessOnboardingRequest:
    business_id: str
    tenant_id: str
    ownership_key: str = "owner"
    region: str = "global"
    channel_kind: ChannelKind | str = ChannelKind.CHATBOT
    adapter_key: str = "chatbot.default"
    external_ref: str = "chatbot.default"
    requested_by: str = "system"
    metadata: Mapping[str, Any] = field(default_factory=dict)
    integration_mode: str = ""
    requested_capabilities: tuple[str, ...] = field(default_factory=tuple)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if not str(self.business_id or "").strip():
            raise ValueError("business_id is required")
        if not str(self.ownership_key or "").strip():
            raise ValueError("ownership_key is required")
        if not str(self.region or "").strip():
            raise ValueError("region is required")
        if not str(self.adapter_key or "").strip():
            raise ValueError("adapter_key is required")
        if not str(self.external_ref or "").strip():
            raise ValueError("external_ref is required")
        if not str(self.requested_by or "").strip():
            raise ValueError("requested_by is required")

    def to_identity(self) -> ChannelIdentity:
        self.validate()
        return ChannelIdentity(
            business_id=self.business_id,
            tenant_id=self.tenant_id,
            channel_kind=_coerce_channel_kind(self.channel_kind),
            adapter_key=self.adapter_key,
            external_ref=self.external_ref,
            region=self.region,
            metadata=dict(self.metadata),
        )


def _coerce_channel_kind(value: ChannelKind | str) -> ChannelKind:
    if isinstance(value, ChannelKind):
        return value
    raw = str(value or "chatbot").strip().lower().replace("-", "_")
    if raw in {"telegram", "webchat", "chat"}:
        return ChannelKind.CHATBOT
    try:
        return ChannelKind(raw)
    except ValueError:
        return ChannelKind.CHATBOT


@dataclass(frozen=True)
class BusinessOnboardingState:
    stage: OnboardingStage
    business_id: str
    tenant_id: str
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BusinessOnboardingResult:
    business_id: str
    tenant_id: str
    states: tuple[BusinessOnboardingState, ...]
    ready: bool
    persistent_surfaces: tuple[str, ...]


__all__ = [
    "BusinessOnboardingRequest",
    "BusinessOnboardingResult",
    "BusinessOnboardingState",
    "OnboardingStage",
]
