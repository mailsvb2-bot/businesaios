from __future__ import annotations

from dataclasses import dataclass

from crm.crm_provider_contract import CrmProvider


@dataclass(frozen=True)
class CrmProviderResolution:
    provider: CrmProvider
    reason: str
    required_capabilities: tuple[str, ...]
