from __future__ import annotations

from dataclasses import dataclass, field

from execution.market_intelligence_models import MarketIntelligenceIngestionRequest


CANON_MARKET_INTELLIGENCE_TENANCY_SCOPE = True


@dataclass(frozen=True)
class MarketIntelligenceTenancyScope:
    tenant_id: str
    allowed_providers: tuple[str, ...] = field(default_factory=tuple)
    allowed_regions: tuple[str, ...] = field(default_factory=tuple)
    default_locale: str | None = None
    max_limit: int = 100

    def apply(self, request: MarketIntelligenceIngestionRequest) -> MarketIntelligenceIngestionRequest:
        if str(request.tenant_id).strip() != str(self.tenant_id).strip():
            raise ValueError('tenant scope mismatch')
        if self.allowed_providers and request.provider not in set(self.allowed_providers):
            raise ValueError(f'provider not allowed for tenant scope: {request.provider}')
        if self.allowed_regions and request.region and request.region not in set(self.allowed_regions):
            raise ValueError(f'region not allowed for tenant scope: {request.region}')
        return MarketIntelligenceIngestionRequest(
            tenant_id=request.tenant_id,
            source_family=request.source_family,
            provider=request.provider,
            action_type=request.action_type,
            query=request.query,
            subject_url=request.subject_url,
            account_ref=request.account_ref,
            region=request.region,
            locale=request.locale or self.default_locale,
            limit=min(int(request.limit), int(self.max_limit)),
            dry_run=bool(request.dry_run),
            metadata=dict(request.metadata or {}),
        )


__all__ = ['CANON_MARKET_INTELLIGENCE_TENANCY_SCOPE', 'MarketIntelligenceTenancyScope']
