from __future__ import annotations

from dataclasses import dataclass

from security.kms_provider_contract import KMSProvider, KMSProviderCapability


CANON_KMS_PROVIDER_REGISTRY = True


@dataclass(frozen=True)
class KMSRegistryEntry:
    provider_name: str
    capability: KMSProviderCapability


class KMSProviderRegistry:
    """Canonical owner of KMS/HSM-ready provider registration."""

    def __init__(self) -> None:
        self._providers: dict[str, KMSProvider] = {}

    def register(self, provider: KMSProvider) -> KMSRegistryEntry:
        capability = provider.capability()
        self._providers[capability.provider_name] = provider
        return KMSRegistryEntry(provider_name=capability.provider_name, capability=capability)

    def get(self, provider_name: str) -> KMSProvider:
        try:
            return self._providers[str(provider_name)]
        except KeyError as exc:
            raise KeyError(f'unknown kms provider: {provider_name}') from exc

    def list_capabilities(self) -> list[KMSProviderCapability]:
        items = [provider.capability() for provider in self._providers.values()]
        items.sort(key=lambda item: item.provider_name)
        return items


__all__ = [
    'CANON_KMS_PROVIDER_REGISTRY',
    'KMSProviderRegistry',
    'KMSRegistryEntry',
]
