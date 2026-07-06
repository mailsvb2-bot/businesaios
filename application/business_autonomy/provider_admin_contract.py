from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from application.business_autonomy.channel_contracts import ChannelKind
from core.tenancy.normalization import require_tenant_id

CANON_PROVIDER_ADMIN_CONTRACT = True


@dataclass(frozen=True)
class ProviderSecretField:
    field_key: str
    secret_name: str
    label: str
    placeholder: str = ""
    required: bool = True
    multiline: bool = False
    secret_kind: str = "token"

    def validate(self) -> None:
        if not str(self.field_key or "").strip():
            raise ValueError("field_key is required")
        if not str(self.secret_name or "").strip():
            raise ValueError("secret_name is required")
        if not str(self.label or "").strip():
            raise ValueError("label is required")


@dataclass(frozen=True)
class ProviderDefinition:
    provider_key: str
    title: str
    connector_id: str
    adapter_key: str
    channel_kind: ChannelKind
    domain: str
    description: str
    secret_fields: tuple[ProviderSecretField, ...]
    default_region: str = "eu-west-1"
    supports_business_onboarding: bool = True
    default_non_ai_mode: str = "supervised"
    default_action_type: str = "internal_execution"
    messaging_channel: str = ""
    messaging_capabilities: Mapping[str, bool] = field(default_factory=dict)
    messaging_live_probe_supported: bool = False

    def validate(self) -> None:
        if not str(self.provider_key or "").strip():
            raise ValueError("provider_key is required")
        if not str(self.title or "").strip():
            raise ValueError("title is required")
        if not str(self.connector_id or "").strip():
            raise ValueError("connector_id is required")
        if not str(self.adapter_key or "").strip():
            raise ValueError("adapter_key is required")
        if not str(self.domain or "").strip():
            raise ValueError("domain is required")
        for secret_field in self.secret_fields:
            secret_field.validate()


@dataclass(frozen=True)
class ProviderCredentialSubmission:
    tenant_id: str
    business_id: str
    provider_key: str
    ownership_key: str
    requested_by: str
    external_ref: str
    region: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    secrets: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if not str(self.business_id or "").strip():
            raise ValueError("business_id is required")
        if not str(self.provider_key or "").strip():
            raise ValueError("provider_key is required")
        if not str(self.ownership_key or "").strip():
            raise ValueError("ownership_key is required")
        if not str(self.requested_by or "").strip():
            raise ValueError("requested_by is required")
        if not str(self.external_ref or "").strip():
            raise ValueError("external_ref is required")


@dataclass(frozen=True)
class ProviderActivationStatus:
    tenant_id: str
    business_id: str
    provider_key: str
    connected: bool
    connector_id: str
    title: str
    channel_kind: str
    secret_fields_bound: tuple[str, ...]
    last_updated_utc: str
    governance_enabled: bool
    persistent_surfaces: tuple[str, ...]
    onboarding_ready: bool
    metadata: Mapping[str, Any] = field(default_factory=dict)


__all__ = [
    "CANON_PROVIDER_ADMIN_CONTRACT",
    "ProviderActivationStatus",
    "ProviderCredentialSubmission",
    "ProviderDefinition",
    "ProviderSecretField",
]
