from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Mapping

from execution.effectors.market_intelligence._base import MarketIntelEffectorBase
from execution.market_intelligence_connector_resolver import MarketIntelligenceConnectorResolver


CANON_MARKET_INTELLIGENCE_EFFECTOR_ROUTER = True

_ACTION_TO_OPERATION = {
    'sync_marketplace_catalog': 'sync_catalog',
    'sync_ads_library': 'sync_ads',
    'sync_competitor_analytics': 'sync_analytics',
    'sync_search_intelligence': 'sync_search_results',
    'sync_professional_discussions': 'sync_discussions',
    'sync_content_publications': 'sync_publications',
    'sync_app_store_intelligence': 'sync_apps',
    'sync_review_intelligence': 'sync_reviews',
    'crawl_competitor_landing': 'crawl_landing_pages',
    'sync_video_platform': 'sync_videos',
    'sync_ads_spy_intelligence': 'sync_ads_spy',
    'sync_newsletter_intelligence': 'sync_newsletters',
}

_ACTION_TO_FAMILY = {
    'sync_marketplace_catalog': 'marketplace',
    'sync_ads_library': 'ads_library',
    'sync_competitor_analytics': 'competitor_analytics',
    'sync_search_intelligence': 'search_intelligence',
    'sync_professional_discussions': 'professional_network',
    'sync_content_publications': 'content_platform',
    'sync_app_store_intelligence': 'app_store',
    'sync_review_intelligence': 'review_platform',
    'crawl_competitor_landing': 'landing_intelligence',
    'sync_video_platform': 'video_platform',
    'sync_ads_spy_intelligence': 'ads_spy',
    'sync_newsletter_intelligence': 'newsletter_intelligence',
}


@dataclass
class MarketIntelligenceProviderRoutedEffector(MarketIntelEffectorBase):
    action_type: str = 'sync_marketplace_catalog'
    external_system: str = 'market_intelligence'
    connector: object | None = None
    operation: str = 'sync_catalog'
    source_family: str = 'marketplace'
    connector_resolver: MarketIntelligenceConnectorResolver = field(default_factory=MarketIntelligenceConnectorResolver)

    def __post_init__(self) -> None:
        return None

    def execute(self, action: Mapping[str, object]):
        payload = dict(action.get('payload') or {}) if isinstance(action.get('payload'), Mapping) else {}
        provider = str(payload.get('provider') or '').strip()
        if not provider:
            raise ValueError('market intelligence provider is required in action.payload.provider')
        self.connector = self.connector_resolver.build(provider)
        self.source_family = _ACTION_TO_FAMILY[self.action_type]
        self.operation = _ACTION_TO_OPERATION[self.action_type]
        return super().execute(action)


@dataclass(frozen=True)
class MarketIntelligenceEffectorRouter:
    def build(self, *, action_type: str):
        normalized = str(action_type or '').strip()
        if normalized not in _ACTION_TO_OPERATION:
            raise KeyError(f'unknown market intelligence action_type: {normalized}')
        return MarketIntelligenceProviderRoutedEffector(
            action_type=normalized,
            operation=_ACTION_TO_OPERATION[normalized],
            source_family=_ACTION_TO_FAMILY[normalized],
        )


__all__ = [
    'CANON_MARKET_INTELLIGENCE_EFFECTOR_ROUTER',
    'MarketIntelligenceEffectorRouter',
    'MarketIntelligenceProviderRoutedEffector',
]
