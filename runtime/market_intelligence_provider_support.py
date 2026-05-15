from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import Any

from runtime.handler_loader import import_internal_attr

CANON_MARKET_INTELLIGENCE_PROVIDER_SUPPORT = True


def _load_internal_attr(module_name: str, attr_name: str) -> Any:
    return import_internal_attr(module_name, attr_name)


@dataclass
class RuntimeMarketIntelligenceProviderSupport:
    _runtime_factory: Any | None = None
    _shared_client: Any | None = None
    _lock: RLock = field(default_factory=RLock)

    def _ensure_runtime_factory(self) -> Any:
        if self._runtime_factory is None:
            ProviderRuntimeFactory = _load_internal_attr(
                'runtime._internal.market_intelligence.provider_runtime',
                'ProviderRuntimeFactory',
            )
            self._runtime_factory = ProviderRuntimeFactory()
        return self._runtime_factory

    def supports(self, provider_key: str) -> bool:
        runtime_factory = self._ensure_runtime_factory()
        return bool(runtime_factory.supports_provider(provider_key))

    def build_client(self, provider_key: str) -> Any | None:
        runtime_factory = self._ensure_runtime_factory()
        if not runtime_factory.supports_provider(provider_key):
            return None
        with self._lock:
            if self._shared_client is None:
                MarketIntelligenceProviderClient = _load_internal_attr(
                    'runtime._internal.market_intelligence.provider_clients',
                    'MarketIntelligenceProviderClient',
                )
                self._shared_client = MarketIntelligenceProviderClient(runtime_factory=runtime_factory)
            return self._shared_client


_DEFAULT_SUPPORT = RuntimeMarketIntelligenceProviderSupport()


def build_default_market_intelligence_provider_client(provider_key: str) -> Any | None:
    return _DEFAULT_SUPPORT.build_client(provider_key)


def market_intelligence_provider_supported(provider_key: str) -> bool:
    return _DEFAULT_SUPPORT.supports(provider_key)


__all__ = [
    'CANON_MARKET_INTELLIGENCE_PROVIDER_SUPPORT',
    'RuntimeMarketIntelligenceProviderSupport',
    'build_default_market_intelligence_provider_client',
    'market_intelligence_provider_supported',
]
