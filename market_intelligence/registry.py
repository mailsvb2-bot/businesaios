from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from market_intelligence.contracts import MarketIntelligenceProvider


@dataclass(frozen=True)
class MarketIntelligenceRegistry:
    """Explicit provider registry; selection remains configuration-driven."""

    providers: dict[str, MarketIntelligenceProvider]

    @classmethod
    def from_providers(
        cls, providers: Iterable[MarketIntelligenceProvider]
    ) -> MarketIntelligenceRegistry:
        resolved: dict[str, MarketIntelligenceProvider] = {}
        for provider in providers:
            key = str(provider.provider_key or '').strip().casefold()
            if not key:
                raise ValueError('market intelligence provider_key must not be blank')
            if key in resolved:
                raise ValueError(f'duplicate market intelligence provider: {key}')
            resolved[key] = provider
        return cls(providers=resolved)

    def get(self, provider_key: str) -> MarketIntelligenceProvider:
        key = provider_key.strip().casefold()
        try:
            return self.providers[key]
        except KeyError as exc:
            raise LookupError(f'Unknown market intelligence provider: {provider_key}') from exc

    def keys(self) -> tuple[str, ...]:
        return tuple(sorted(self.providers))
