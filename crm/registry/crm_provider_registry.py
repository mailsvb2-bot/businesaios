from __future__ import annotations

from dataclasses import dataclass

from crm.crm_provider_contract import CrmProvider


@dataclass
class CrmProviderRegistry:
    providers: dict[str, CrmProvider]

    @classmethod
    def from_catalog(cls, catalog: tuple[CrmProvider, ...]) -> 'CrmProviderRegistry':
        return cls(providers={provider.provider_key: provider for provider in catalog})

    def get(self, provider_key: str) -> CrmProvider:
        try:
            return self.providers[provider_key]
        except KeyError as exc:
            raise LookupError(f'Unknown CRM provider: {provider_key}') from exc

    def keys(self) -> tuple[str, ...]:
        return tuple(sorted(self.providers))

    def list_enabled(self) -> tuple[CrmProvider, ...]:
        return tuple(provider for provider in self.providers.values() if provider.enabled)
