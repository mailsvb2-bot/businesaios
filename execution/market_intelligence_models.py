from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from contracts.platforms.market_intelligence_contract import normalize_source_family


CANON_MARKET_INTELLIGENCE_MODELS = True


@dataclass(frozen=True)
class MarketIntelligenceIngestionRequest:
    tenant_id: str
    source_family: str
    provider: str
    action_type: str
    query: str | None = None
    subject_url: str | None = None
    account_ref: str | None = None
    region: str | None = None
    locale: str | None = None
    limit: int = 25
    dry_run: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, 'tenant_id', str(self.tenant_id or '').strip() or 'default')
        object.__setattr__(self, 'source_family', normalize_source_family(self.source_family))
        object.__setattr__(self, 'provider', str(self.provider or '').strip())
        object.__setattr__(self, 'action_type', str(self.action_type or '').strip())
        object.__setattr__(self, 'query', str(self.query or '').strip() or None)
        object.__setattr__(self, 'subject_url', str(self.subject_url or '').strip() or None)
        object.__setattr__(self, 'account_ref', str(self.account_ref or '').strip() or None)
        object.__setattr__(self, 'region', str(self.region or '').strip() or None)
        object.__setattr__(self, 'locale', str(self.locale or '').strip() or None)
        object.__setattr__(self, 'limit', max(1, min(int(self.limit), 250)))
        object.__setattr__(self, 'dry_run', bool(self.dry_run))
        object.__setattr__(self, 'metadata', dict(self.metadata or {}))

    def as_payload(self) -> dict[str, Any]:
        return {
            'tenant_id': self.tenant_id,
            'query': self.query,
            'subject_url': self.subject_url,
            'account_ref': self.account_ref,
            'region': self.region,
            'locale': self.locale,
            'limit': self.limit,
            'metadata': dict(self.metadata),
        }


@dataclass(frozen=True)
class MarketIntelligenceDatasetRow:
    source_family: str
    provider: str
    record_id: str
    text: str
    features: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            'source_family': self.source_family,
            'provider': self.provider,
            'record_id': self.record_id,
            'text': self.text,
            'features': dict(self.features),
        }


__all__ = ['CANON_MARKET_INTELLIGENCE_MODELS', 'MarketIntelligenceDatasetRow', 'MarketIntelligenceIngestionRequest']
