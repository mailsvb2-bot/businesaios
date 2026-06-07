from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from collections.abc import Mapping

CANON_MARKET_INTELLIGENCE_CONTRACT = True

SOURCE_FAMILIES: tuple[str, ...] = ('marketplace', 'ads_library', 'competitor_analytics', 'search_intelligence', 'professional_network', 'content_platform', 'app_store', 'review_platform', 'landing_intelligence', 'video_platform', 'ads_spy', 'newsletter_intelligence')


def _clean_text(value: object, *, field_name: str) -> str:
    text = str(value or '').strip()
    if not text:
        raise ValueError(f'{field_name} is required')
    return text


def _clean_optional_text(value: object | None) -> str | None:
    text = str(value or '').strip()
    return text or None


def _safe_dict(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(value or {})


def normalize_source_family(value: object, *, field_name: str = 'source_family') -> str:
    family = _clean_text(value, field_name=field_name).lower()
    if family not in set(SOURCE_FAMILIES):
        raise ValueError(f'unsupported source_family: {family}')
    return family


@dataclass(frozen=True)
class MarketIntelligenceTarget:
    source_family: str
    provider: str
    tenant_id: str
    query: str | None = None
    subject_url: str | None = None
    account_ref: str | None = None
    region: str | None = None
    locale: str | None = None
    limit: int = 25
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, 'source_family', normalize_source_family(self.source_family))
        object.__setattr__(self, 'provider', _clean_text(self.provider, field_name='provider'))
        object.__setattr__(self, 'tenant_id', _clean_text(self.tenant_id, field_name='tenant_id'))
        object.__setattr__(self, 'query', _clean_optional_text(self.query))
        object.__setattr__(self, 'subject_url', _clean_optional_text(self.subject_url))
        object.__setattr__(self, 'account_ref', _clean_optional_text(self.account_ref))
        object.__setattr__(self, 'region', _clean_optional_text(self.region))
        object.__setattr__(self, 'locale', _clean_optional_text(self.locale))
        object.__setattr__(self, 'limit', max(1, min(int(self.limit), 250)))
        object.__setattr__(self, 'metadata', _safe_dict(self.metadata))

    def as_dict(self) -> dict[str, Any]:
        return {
            'source_family': self.source_family,
            'provider': self.provider,
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
class MarketIntelligenceRecord:
    source_family: str
    provider: str
    external_id: str
    title: str = ''
    body: str = ''
    url: str | None = None
    price: float | None = None
    rating: float | None = None
    currency: str | None = None
    evidence: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    tags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, 'source_family', normalize_source_family(self.source_family))
        object.__setattr__(self, 'provider', _clean_text(self.provider, field_name='provider'))
        object.__setattr__(self, 'external_id', _clean_text(self.external_id, field_name='external_id'))
        object.__setattr__(self, 'title', str(self.title or '').strip())
        object.__setattr__(self, 'body', str(self.body or '').strip())
        object.__setattr__(self, 'url', _clean_optional_text(self.url))
        object.__setattr__(self, 'currency', _clean_optional_text(self.currency))
        object.__setattr__(self, 'evidence', _safe_dict(self.evidence))
        object.__setattr__(self, 'metadata', _safe_dict(self.metadata))
        object.__setattr__(self, 'tags', tuple(sorted({str(item).strip() for item in self.tags if str(item).strip()})))
        if self.price is not None:
            object.__setattr__(self, 'price', float(self.price))
        if self.rating is not None:
            object.__setattr__(self, 'rating', float(self.rating))

    def as_dict(self) -> dict[str, Any]:
        return {
            'source_family': self.source_family,
            'provider': self.provider,
            'external_id': self.external_id,
            'title': self.title,
            'body': self.body,
            'url': self.url,
            'price': self.price,
            'rating': self.rating,
            'currency': self.currency,
            'evidence': dict(self.evidence),
            'metadata': dict(self.metadata),
            'tags': list(self.tags),
        }


@dataclass(frozen=True)
class MarketIntelligenceEnvelope:
    connector_id: str
    provider: str
    source_family: str
    operation: str
    target: MarketIntelligenceTarget
    records: tuple[MarketIntelligenceRecord, ...] = field(default_factory=tuple)
    cursor: str | None = None
    summary: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, 'connector_id', _clean_text(self.connector_id, field_name='connector_id'))
        object.__setattr__(self, 'provider', _clean_text(self.provider, field_name='provider'))
        object.__setattr__(self, 'source_family', normalize_source_family(self.source_family))
        object.__setattr__(self, 'operation', _clean_text(self.operation, field_name='operation'))
        object.__setattr__(self, 'records', tuple(self.records))
        object.__setattr__(self, 'cursor', _clean_optional_text(self.cursor))
        object.__setattr__(self, 'summary', _safe_dict(self.summary))
        object.__setattr__(self, 'metadata', _safe_dict(self.metadata))

    def as_dict(self) -> dict[str, Any]:
        return {
            'connector_id': self.connector_id,
            'provider': self.provider,
            'source_family': self.source_family,
            'operation': self.operation,
            'target': self.target.as_dict(),
            'records': [record.as_dict() for record in self.records],
            'cursor': self.cursor,
            'summary': dict(self.summary),
            'metadata': dict(self.metadata),
        }


__all__ = [
    'CANON_MARKET_INTELLIGENCE_CONTRACT',
    'SOURCE_FAMILIES',
    'MarketIntelligenceEnvelope',
    'MarketIntelligenceRecord',
    'MarketIntelligenceTarget',
    'normalize_source_family',
]
