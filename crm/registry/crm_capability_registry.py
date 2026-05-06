from __future__ import annotations

from dataclasses import dataclass

from crm.crm_capability_contract import CrmCapabilityDescriptor
from crm.registry.crm_provider_registry import CrmProviderRegistry


@dataclass(frozen=True)
class CrmCapabilityRegistry:
    provider_registry: CrmProviderRegistry

    def for_provider(self, provider_key: str) -> CrmCapabilityDescriptor:
        return self.provider_registry.get(provider_key).capability_descriptor

    def providers_supporting(self, capability_name: str) -> tuple[str, ...]:
        return tuple(
            provider.provider_key
            for provider in self.provider_registry.list_enabled()
            if provider.capability_descriptor.supports(capability_name)
        )
