from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from runtime.market_intelligence_provider_support import (
    RuntimeMarketIntelligenceProviderSupport,
    build_default_market_intelligence_provider_client,
    market_intelligence_provider_supported,
)

CANON_MARKET_INTELLIGENCE_PROVIDER_FACTORY = True


class StaticProviderFactory:
    def __init__(self, providers: Mapping[str, Any] | None = None) -> None:
        self._providers = dict(providers or {})

    def build(self, *, provider_key: str) -> Any | None:
        return self._providers.get(str(provider_key).strip())


@dataclass
class RuntimeBackedProviderFactory:
    runtime_support: RuntimeMarketIntelligenceProviderSupport = field(default_factory=RuntimeMarketIntelligenceProviderSupport)

    def build(self, *, provider_key: str) -> Any | None:
        return self.runtime_support.build_client(provider_key)

    def supports(self, provider_key: str) -> bool:
        return self.runtime_support.supports(provider_key)


_DEFAULT_RUNTIME_PROVIDER_FACTORY = RuntimeBackedProviderFactory()


def build_default_provider_client(provider_key: str) -> Any | None:
    return build_default_market_intelligence_provider_client(provider_key)


def provider_supported(provider_key: str) -> bool:
    return market_intelligence_provider_supported(provider_key)


__all__ = [
    'CANON_MARKET_INTELLIGENCE_PROVIDER_FACTORY',
    'RuntimeBackedProviderFactory',
    'StaticProviderFactory',
    'build_default_provider_client',
    'provider_supported',
]
