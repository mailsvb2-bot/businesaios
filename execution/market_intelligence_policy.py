from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from contracts.platforms.market_intelligence_contract import SOURCE_FAMILIES, normalize_source_family
from execution.market_intelligence_models import MarketIntelligenceIngestionRequest


CANON_MARKET_INTELLIGENCE_POLICY = True

_ALLOWED_ACTIONS: dict[str, str] = {
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

_ALLOWED_PROVIDERS: dict[str, tuple[str, ...]] = {
    'marketplace': ('amazon', 'ebay', 'etsy', 'aliexpress', 'wildberries', 'ozon', 'shopify_store', 'woocommerce_store'),
    'ads_library': ('facebook_ad_library', 'tiktok_ads_library', 'google_ads_preview', 'linkedin_ads_library', 'pinterest_ads_library'),
    'competitor_analytics': ('similarweb', 'ahrefs', 'semrush', 'ubersuggest'),
    'search_intelligence': ('google_search', 'bing_search', 'duckduckgo_search', 'google_trends'),
    'professional_network': ('linkedin_network', 'x_network', 'reddit', 'quora'),
    'content_platform': ('medium', 'substack_publications', 'notion_public_docs', 'github_open_products'),
    'app_store': ('google_play', 'apple_app_store', 'app_store'),
    'review_platform': ('trustpilot', 'g2', 'capterra', 'yelp'),
    'landing_intelligence': ('public_landing_pages',),
    'video_platform': ('vimeo', 'rumble', 'dailymotion', 'twitch'),
    'ads_spy': ('adspy', 'bigspy', 'poweradspy'),
    'newsletter_intelligence': ('substack_newsletters', 'beehiiv', 'convertkit_public', 'mailchimp_public'),
}


@dataclass(frozen=True)
class MarketIntelligencePolicy:
    max_limit: int = 100
    enabled_families: tuple[str, ...] = field(default_factory=lambda: tuple(SOURCE_FAMILIES))

    def validate_request(self, request: MarketIntelligenceIngestionRequest) -> MarketIntelligenceIngestionRequest:
        family = normalize_source_family(request.source_family)
        if family not in set(self.enabled_families):
            raise ValueError(f'source_family disabled by policy: {family}')
        expected_family = _ALLOWED_ACTIONS.get(str(request.action_type).strip())
        if expected_family != family:
            raise ValueError('action_type/source_family mismatch')
        if request.provider not in set(_ALLOWED_PROVIDERS.get(family, ())):
            raise ValueError(f'provider not allowed for family: {request.provider}')
        if request.limit > int(self.max_limit):
            raise ValueError(f'limit exceeds policy max_limit={self.max_limit}')
        return request

    def allowed_connector_id(self, request: MarketIntelligenceIngestionRequest) -> str:
        return str(request.provider).strip()

    def summarize_result(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        records = list(payload.get('records') or []) if isinstance(payload, Mapping) else []
        prices = [float(item.get('price')) for item in records if isinstance(item, Mapping) and item.get('price') is not None]
        ratings = [float(item.get('rating')) for item in records if isinstance(item, Mapping) and item.get('rating') is not None]
        return {
            'records_count': len(records),
            'avg_price': (sum(prices) / len(prices)) if prices else None,
            'avg_rating': (sum(ratings) / len(ratings)) if ratings else None,
            'providers_seen': sorted({str(item.get('provider') or '').strip() for item in records if isinstance(item, Mapping)}),
        }


__all__ = ['CANON_MARKET_INTELLIGENCE_POLICY', 'MarketIntelligencePolicy']
