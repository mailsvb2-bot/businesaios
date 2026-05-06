from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from execution.market_intelligence_models import MarketIntelligenceIngestionRequest


CANON_MARKET_INTELLIGENCE_QUOTA_GUARD = True


@dataclass
class MarketIntelligenceQuotaGuard:
    max_requests_per_tenant: int = 500
    max_requests_per_provider: int = 250
    max_requests_per_family: int = 400
    max_limit_per_request: int = 100
    _tenant_counters: dict[str, int] = field(default_factory=dict)
    _provider_counters: dict[tuple[str, str], int] = field(default_factory=dict)
    _family_counters: dict[tuple[str, str], int] = field(default_factory=dict)

    def consume(self, request: MarketIntelligenceIngestionRequest) -> None:
        tenant_id = str(request.tenant_id).strip() or 'default'
        provider = str(request.provider).strip()
        family = str(request.source_family).strip()
        tenant_used = int(self._tenant_counters.get(tenant_id, 0))
        if tenant_used >= int(self.max_requests_per_tenant):
            raise ValueError(f'tenant quota exceeded: {tenant_id}')
        provider_key = (tenant_id, provider)
        provider_used = int(self._provider_counters.get(provider_key, 0))
        if provider_used >= int(self.max_requests_per_provider):
            raise ValueError(f'provider quota exceeded: {provider}')
        family_key = (tenant_id, family)
        family_used = int(self._family_counters.get(family_key, 0))
        if family_used >= int(self.max_requests_per_family):
            raise ValueError(f'family quota exceeded: {family}')
        if int(request.limit) > int(self.max_limit_per_request):
            raise ValueError('request limit exceeds quota guard')
        self._tenant_counters[tenant_id] = tenant_used + 1
        self._provider_counters[provider_key] = provider_used + 1
        self._family_counters[family_key] = family_used + 1

    def snapshot(self) -> dict[str, Mapping[str, int]]:
        return {
            'tenant': dict(self._tenant_counters),
            'provider': {f'{tenant}:{provider}': value for (tenant, provider), value in self._provider_counters.items()},
            'family': {f'{tenant}:{family}': value for (tenant, family), value in self._family_counters.items()},
        }


__all__ = ['CANON_MARKET_INTELLIGENCE_QUOTA_GUARD', 'MarketIntelligenceQuotaGuard']
