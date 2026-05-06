from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class CrmCapabilityDescriptor:
    provider_key: str
    can_read_contacts: bool = False
    can_write_contacts: bool = False
    can_read_deals: bool = False
    can_write_deals: bool = False
    can_read_pipelines: bool = False
    can_write_pipelines: bool = False
    can_verify_writes: bool = False
    can_receive_webhooks: bool = False
    can_oauth_connect: bool = False
    supports_idempotency: bool = False
    maturity: str = 'capability_shell'
    metadata: Mapping[str, object] = field(default_factory=dict)

    def supports(self, capability_name: str) -> bool:
        return bool(getattr(self, capability_name, False))
