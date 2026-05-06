from __future__ import annotations

from dataclasses import dataclass, field

from contracts.platforms.market_intelligence_contract import SOURCE_FAMILIES, normalize_source_family


CANON_MARKET_INTELLIGENCE_PROVIDER_MATRIX = True


PROVIDERS_BY_FAMILY: dict[str, tuple[str, ...]] = {
    'marketplace': ('amazon', 'ebay', 'etsy', 'aliexpress', 'wildberries', 'ozon', 'shopify', 'woocommerce'),
    'ads_library': ('meta', 'facebook_ad_library', 'tiktok', 'tiktok_ads_library', 'google', 'google_ads_preview', 'linkedin', 'linkedin_ads_library', 'pinterest', 'pinterest_ads_library'),
    'competitor_analytics': ('similarweb', 'ahrefs', 'semrush', 'ubersuggest'),
    'search_intelligence': ('google', 'google_search', 'bing', 'bing_search', 'duckduckgo', 'duckduckgo_search', 'google_trends'),
    'professional_network': ('linkedin', 'x', 'reddit', 'quora'),
    'content_platform': ('medium', 'substack', 'substack_publications', 'notion', 'notion_public_docs', 'github', 'github_open_products'),
    'app_store': ('google', 'google_play', 'apple', 'apple_app_store', 'app_store'),
    'review_platform': ('trustpilot', 'g2', 'capterra', 'yelp'),
    'landing_intelligence': ('web', 'public_web', 'public_landing_pages'),
    'video_platform': ('vimeo', 'rumble', 'dailymotion', 'twitch'),
    'ads_spy': ('adspy', 'bigspy', 'poweradspy'),
    'newsletter_intelligence': ('substack', 'substack_newsletters', 'beehiiv', 'convertkit', 'convertkit_public', 'mailchimp', 'mailchimp_public'),
}

ACTION_TO_FAMILY: dict[str, str] = {
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


@dataclass(frozen=True)
class MarketIntelligenceProviderMatrix:
    providers_by_family: dict[str, tuple[str, ...]] = field(default_factory=lambda: dict(PROVIDERS_BY_FAMILY))
    action_to_family: dict[str, str] = field(default_factory=lambda: dict(ACTION_TO_FAMILY))

    def supported_families(self) -> tuple[str, ...]:
        return tuple(family for family in SOURCE_FAMILIES if family in self.providers_by_family)

    def providers_for_family(self, family: str) -> tuple[str, ...]:
        normalized_family = normalize_source_family(family)
        return tuple(self.providers_by_family.get(normalized_family, ()))

    def validate(self, *, source_family: str, provider: str, action_type: str) -> None:
        normalized_family = normalize_source_family(source_family)
        provider_text = str(provider or '').strip()
        action_text = str(action_type or '').strip()
        if not provider_text:
            raise ValueError('provider is required')
        if not action_text:
            raise ValueError('action_type is required')
        allowed_providers = set(self.providers_for_family(normalized_family))
        if provider_text not in allowed_providers:
            raise ValueError(f'provider {provider_text!r} is not allowed for source_family {normalized_family!r}')
        expected_family = self.action_to_family.get(action_text)
        if expected_family is None:
            raise ValueError(f'unsupported market_intelligence action_type: {action_text}')
        if expected_family != normalized_family:
            raise ValueError(f'action_type {action_text!r} does not match source_family {normalized_family!r}')


__all__ = [
    'ACTION_TO_FAMILY',
    'CANON_MARKET_INTELLIGENCE_PROVIDER_MATRIX',
    'MarketIntelligenceProviderMatrix',
    'PROVIDERS_BY_FAMILY',
]
