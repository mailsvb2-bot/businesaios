from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from enum import Enum


class ProviderAuthKind(str, Enum):
    NONE = "none"
    API_KEY_HEADER = "api_key_header"
    API_KEY_QUERY = "api_key_query"
    BEARER_TOKEN = "bearer_token"
    BASIC = "basic"


CANON_MARKET_INTELLIGENCE_PROVIDER_CATALOG = True


@dataclass(frozen=True)
class ProviderCatalogEntry:
    provider: str
    source_family: str
    primary_operation: str
    env_base_url_key: str
    default_base_url: str
    auth_kind: ProviderAuthKind = ProviderAuthKind.NONE
    secret_ref_primary: str | None = None
    secret_ref_secondary: str | None = None
    query_param_name: str | None = None
    header_name: str | None = None
    header_value_template: str | None = None
    basic_username_ref: str | None = None
    basic_password_ref: str | None = None
    stable_version_header_name: str | None = "X-Api-Version"
    stable_version_header_value: str | None = "2026-01"
    compliance_classification: str = "public_web"
    robots_sensitive: bool = False
    terms_sensitive: bool = False
    supports_rate_limit_headers: bool = True
    metadata: Mapping[str, Any] | None = None


FAMILY_OPERATIONS: dict[str, tuple[str, ...]] = {
    "marketplace": ("sync_catalog", "fetch_listing", "fetch_reviews", "fetch_pricing", "fetch_images"),
    "ads_library": ("sync_ads", "fetch_creative", "fetch_landing_url", "fetch_engagement"),
    "competitor_analytics": ("sync_analytics", "fetch_keywords", "fetch_top_pages", "fetch_backlinks", "fetch_ads"),
    "search_intelligence": ("sync_search_results", "fetch_keywords", "fetch_trends", "fetch_related_queries"),
    "professional_network": ("sync_discussions", "fetch_posts", "fetch_questions", "fetch_objections"),
    "content_platform": ("sync_publications", "fetch_articles", "fetch_docs", "fetch_repos"),
    "app_store": ("sync_apps", "fetch_reviews", "fetch_features", "fetch_pricing"),
    "review_platform": ("sync_reviews", "fetch_ratings", "fetch_objections", "fetch_use_cases"),
    "landing_intelligence": ("crawl_landing_pages", "fetch_pricing", "fetch_offers", "fetch_cta_structure"),
    "video_platform": ("sync_videos", "fetch_transcript", "fetch_metadata", "fetch_comments"),
    "ads_spy": ("sync_ads_spy", "fetch_creatives", "fetch_cta", "fetch_landing_url"),
    "newsletter_intelligence": ("sync_newsletters", "fetch_editions", "fetch_offers", "fetch_cta"),
}


PROVIDER_ALIASES: dict[str, str] = {
    "meta": "facebook_ad_library",
    "google": "google_search",
    "apple": "apple_app_store",
    "web": "public_landing_pages",
    "substack": "substack_newsletters",
    "linkedin": "linkedin_network",
    "tiktok": "tiktok_ads_library",
    "pinterest": "pinterest_ads_library",
    "shopify": "shopify_store",
    "woocommerce": "woocommerce_store",
}


PROVIDER_CATALOG: dict[str, ProviderCatalogEntry] = {
    "amazon": ProviderCatalogEntry("amazon", "marketplace", "sync_catalog", "MI_AMAZON_BASE_URL", "https://api.amazon.example.invalid", ProviderAuthKind.BEARER_TOKEN, "AMAZON_MARKET_TOKEN", compliance_classification="partner_or_public"),
    "ebay": ProviderCatalogEntry("ebay", "marketplace", "sync_catalog", "MI_EBAY_BASE_URL", "https://api.ebay.example.invalid", ProviderAuthKind.BEARER_TOKEN, "EBAY_MARKET_TOKEN", compliance_classification="partner_or_public"),
    "etsy": ProviderCatalogEntry("etsy", "marketplace", "sync_catalog", "MI_ETSY_BASE_URL", "https://api.etsy.example.invalid", ProviderAuthKind.API_KEY_HEADER, "ETSY_API_KEY", header_name="X-Api-Key", compliance_classification="partner_or_public"),
    "aliexpress": ProviderCatalogEntry("aliexpress", "marketplace", "sync_catalog", "MI_ALIEXPRESS_BASE_URL", "https://api.aliexpress.example.invalid", ProviderAuthKind.API_KEY_QUERY, "ALIEXPRESS_API_KEY", query_param_name="api_key", compliance_classification="partner_or_public"),
    "wildberries": ProviderCatalogEntry("wildberries", "marketplace", "sync_catalog", "MI_WILDBERRIES_BASE_URL", "https://api.wildberries.example.invalid", ProviderAuthKind.API_KEY_HEADER, "WILDBERRIES_API_KEY", header_name="X-Api-Key", compliance_classification="partner_or_public"),
    "ozon": ProviderCatalogEntry("ozon", "marketplace", "sync_catalog", "MI_OZON_BASE_URL", "https://api.ozon.example.invalid", ProviderAuthKind.API_KEY_HEADER, "OZON_API_KEY", header_name="X-Api-Key", compliance_classification="partner_or_public"),
    "shopify_store": ProviderCatalogEntry("shopify_store", "marketplace", "sync_catalog", "MI_SHOPIFY_STORE_BASE_URL", "https://api.shopify-store.example.invalid", ProviderAuthKind.BEARER_TOKEN, "SHOPIFY_STORE_TOKEN", compliance_classification="partner_or_public"),
    "woocommerce_store": ProviderCatalogEntry("woocommerce_store", "marketplace", "sync_catalog", "MI_WOOCOMMERCE_STORE_BASE_URL", "https://api.woocommerce-store.example.invalid", ProviderAuthKind.BASIC, None, None, None, None, None, "WOOCOMMERCE_STORE_USERNAME", "WOOCOMMERCE_STORE_PASSWORD", compliance_classification="partner_or_public"),
    "facebook_ad_library": ProviderCatalogEntry("facebook_ad_library", "ads_library", "sync_ads", "MI_FACEBOOK_AD_LIBRARY_BASE_URL", "https://api.facebook-ad-library.example.invalid", ProviderAuthKind.BEARER_TOKEN, "META_AD_LIBRARY_TOKEN", compliance_classification="public_ads_library", terms_sensitive=True),
    "tiktok_ads_library": ProviderCatalogEntry("tiktok_ads_library", "ads_library", "sync_ads", "MI_TIKTOK_AD_LIBRARY_BASE_URL", "https://api.tiktok-ad-library.example.invalid", ProviderAuthKind.API_KEY_HEADER, "TIKTOK_AD_LIBRARY_API_KEY", header_name="X-Api-Key", compliance_classification="public_ads_library", terms_sensitive=True),
    "google_ads_preview": ProviderCatalogEntry("google_ads_preview", "ads_library", "sync_ads", "MI_GOOGLE_ADS_PREVIEW_BASE_URL", "https://api.google-ads-preview.example.invalid", ProviderAuthKind.API_KEY_QUERY, "GOOGLE_ADS_PREVIEW_API_KEY", query_param_name="key", compliance_classification="public_ads_library", terms_sensitive=True),
    "linkedin_ads_library": ProviderCatalogEntry("linkedin_ads_library", "ads_library", "sync_ads", "MI_LINKEDIN_ADS_LIBRARY_BASE_URL", "https://api.linkedin-ads-library.example.invalid", ProviderAuthKind.BEARER_TOKEN, "LINKEDIN_ADS_LIBRARY_TOKEN", compliance_classification="public_ads_library", terms_sensitive=True),
    "pinterest_ads_library": ProviderCatalogEntry("pinterest_ads_library", "ads_library", "sync_ads", "MI_PINTEREST_ADS_LIBRARY_BASE_URL", "https://api.pinterest-ads-library.example.invalid", ProviderAuthKind.BEARER_TOKEN, "PINTEREST_ADS_LIBRARY_TOKEN", compliance_classification="public_ads_library", terms_sensitive=True),
    "similarweb": ProviderCatalogEntry("similarweb", "competitor_analytics", "sync_analytics", "MI_SIMILARWEB_BASE_URL", "https://api.similarweb.example.invalid", ProviderAuthKind.API_KEY_HEADER, "SIMILARWEB_API_KEY", header_name="X-Api-Key", compliance_classification="licensed_analytics"),
    "ahrefs": ProviderCatalogEntry("ahrefs", "competitor_analytics", "sync_analytics", "MI_AHREFS_BASE_URL", "https://api.ahrefs.example.invalid", ProviderAuthKind.API_KEY_HEADER, "AHREFS_API_KEY", header_name="X-Api-Key", compliance_classification="licensed_analytics"),
    "semrush": ProviderCatalogEntry("semrush", "competitor_analytics", "sync_analytics", "MI_SEMRUSH_BASE_URL", "https://api.semrush.example.invalid", ProviderAuthKind.API_KEY_QUERY, "SEMRUSH_API_KEY", query_param_name="key", compliance_classification="licensed_analytics"),
    "ubersuggest": ProviderCatalogEntry("ubersuggest", "competitor_analytics", "sync_analytics", "MI_UBERSUGGEST_BASE_URL", "https://api.ubersuggest.example.invalid", ProviderAuthKind.API_KEY_HEADER, "UBERSUGGEST_API_KEY", header_name="X-Api-Key", compliance_classification="licensed_analytics"),
    "google_search": ProviderCatalogEntry("google_search", "search_intelligence", "sync_search_results", "MI_GOOGLE_SEARCH_BASE_URL", "https://api.google-search.example.invalid", ProviderAuthKind.API_KEY_QUERY, "GOOGLE_SEARCH_API_KEY", query_param_name="key", compliance_classification="search_api"),
    "bing_search": ProviderCatalogEntry("bing_search", "search_intelligence", "sync_search_results", "MI_BING_SEARCH_BASE_URL", "https://api.bing-search.example.invalid", ProviderAuthKind.API_KEY_HEADER, "BING_SEARCH_API_KEY", header_name="Ocp-Apim-Subscription-Key", compliance_classification="search_api"),
    "duckduckgo_search": ProviderCatalogEntry("duckduckgo_search", "search_intelligence", "sync_search_results", "MI_DUCKDUCKGO_SEARCH_BASE_URL", "https://api.duckduckgo-search.example.invalid", ProviderAuthKind.NONE, compliance_classification="search_api"),
    "google_trends": ProviderCatalogEntry("google_trends", "search_intelligence", "sync_search_results", "MI_GOOGLE_TRENDS_BASE_URL", "https://api.google-trends.example.invalid", ProviderAuthKind.API_KEY_QUERY, "GOOGLE_TRENDS_API_KEY", query_param_name="key", compliance_classification="search_api"),
    "linkedin_network": ProviderCatalogEntry("linkedin_network", "professional_network", "sync_discussions", "MI_LINKEDIN_NETWORK_BASE_URL", "https://api.linkedin-network.example.invalid", ProviderAuthKind.BEARER_TOKEN, "LINKEDIN_NETWORK_TOKEN", compliance_classification="public_platform", terms_sensitive=True),
    "x_network": ProviderCatalogEntry("x_network", "professional_network", "sync_discussions", "MI_X_NETWORK_BASE_URL", "https://api.x-network.example.invalid", ProviderAuthKind.BEARER_TOKEN, "X_NETWORK_TOKEN", compliance_classification="public_platform", terms_sensitive=True),
    "reddit": ProviderCatalogEntry("reddit", "professional_network", "sync_discussions", "MI_REDDIT_BASE_URL", "https://oauth.reddit.example.invalid", ProviderAuthKind.BEARER_TOKEN, "REDDIT_TOKEN", compliance_classification="public_platform", terms_sensitive=True),
    "quora": ProviderCatalogEntry("quora", "professional_network", "sync_discussions", "MI_QUORA_BASE_URL", "https://api.quora.example.invalid", ProviderAuthKind.NONE, compliance_classification="public_platform", terms_sensitive=True),
    "medium": ProviderCatalogEntry("medium", "content_platform", "sync_publications", "MI_MEDIUM_BASE_URL", "https://api.medium.example.invalid", ProviderAuthKind.NONE, compliance_classification="public_content"),
    "substack_publications": ProviderCatalogEntry("substack_publications", "content_platform", "sync_publications", "MI_SUBSTACK_PUBLICATIONS_BASE_URL", "https://api.substack-publications.example.invalid", ProviderAuthKind.NONE, compliance_classification="public_content", terms_sensitive=True),
    "notion_public_docs": ProviderCatalogEntry("notion_public_docs", "content_platform", "sync_publications", "MI_NOTION_PUBLIC_DOCS_BASE_URL", "https://api.notion-public-docs.example.invalid", ProviderAuthKind.NONE, compliance_classification="public_content"),
    "github_open_products": ProviderCatalogEntry("github_open_products", "content_platform", "sync_publications", "MI_GITHUB_OPEN_PRODUCTS_BASE_URL", "https://api.github-open-products.example.invalid", ProviderAuthKind.BEARER_TOKEN, "GITHUB_OPEN_PRODUCTS_TOKEN", compliance_classification="public_content"),
    "google_play": ProviderCatalogEntry("google_play", "app_store", "sync_apps", "MI_GOOGLE_PLAY_BASE_URL", "https://api.google-play.example.invalid", ProviderAuthKind.NONE, compliance_classification="app_store_public"),
    "app_store": ProviderCatalogEntry("app_store", "app_store", "sync_apps", "MI_APP_STORE_BASE_URL", "https://api.app-store.example.invalid", ProviderAuthKind.NONE, compliance_classification="app_store_public"),
    "apple_app_store": ProviderCatalogEntry("apple_app_store", "app_store", "sync_apps", "MI_APPLE_APP_STORE_BASE_URL", "https://api.apple-app-store.example.invalid", ProviderAuthKind.NONE, compliance_classification="app_store_public"),
    "trustpilot": ProviderCatalogEntry("trustpilot", "review_platform", "sync_reviews", "MI_TRUSTPILOT_BASE_URL", "https://api.trustpilot.example.invalid", ProviderAuthKind.API_KEY_HEADER, "TRUSTPILOT_API_KEY", header_name="X-Api-Key", compliance_classification="review_platform_public", terms_sensitive=True),
    "g2": ProviderCatalogEntry("g2", "review_platform", "sync_reviews", "MI_G2_BASE_URL", "https://api.g2.example.invalid", ProviderAuthKind.API_KEY_HEADER, "G2_API_KEY", header_name="X-Api-Key", compliance_classification="review_platform_public", terms_sensitive=True),
    "capterra": ProviderCatalogEntry("capterra", "review_platform", "sync_reviews", "MI_CAPTERRA_BASE_URL", "https://api.capterra.example.invalid", ProviderAuthKind.NONE, compliance_classification="review_platform_public", terms_sensitive=True),
    "yelp": ProviderCatalogEntry("yelp", "review_platform", "sync_reviews", "MI_YELP_BASE_URL", "https://api.yelp.example.invalid", ProviderAuthKind.BEARER_TOKEN, "YELP_TOKEN", compliance_classification="review_platform_public", terms_sensitive=True),
    "public_landing_pages": ProviderCatalogEntry("public_landing_pages", "landing_intelligence", "crawl_landing_pages", "MI_PUBLIC_LANDING_BASE_URL", "https://crawler.example.invalid", ProviderAuthKind.NONE, compliance_classification="public_web", robots_sensitive=True),
    "vimeo": ProviderCatalogEntry("vimeo", "video_platform", "sync_videos", "MI_VIMEO_BASE_URL", "https://api.vimeo.example.invalid", ProviderAuthKind.BEARER_TOKEN, "VIMEO_TOKEN", compliance_classification="public_video"),
    "rumble": ProviderCatalogEntry("rumble", "video_platform", "sync_videos", "MI_RUMBLE_BASE_URL", "https://api.rumble.example.invalid", ProviderAuthKind.NONE, compliance_classification="public_video"),
    "dailymotion": ProviderCatalogEntry("dailymotion", "video_platform", "sync_videos", "MI_DAILYMOTION_BASE_URL", "https://api.dailymotion.example.invalid", ProviderAuthKind.NONE, compliance_classification="public_video"),
    "twitch": ProviderCatalogEntry("twitch", "video_platform", "sync_videos", "MI_TWITCH_BASE_URL", "https://api.twitch.example.invalid", ProviderAuthKind.BEARER_TOKEN, "TWITCH_TOKEN", compliance_classification="public_video"),
    "adspy": ProviderCatalogEntry("adspy", "ads_spy", "sync_ads_spy", "MI_ADSPY_BASE_URL", "https://api.adspy.example.invalid", ProviderAuthKind.API_KEY_QUERY, "ADSPY_API_KEY", query_param_name="api_key", compliance_classification="licensed_ads_spy"),
    "bigspy": ProviderCatalogEntry("bigspy", "ads_spy", "sync_ads_spy", "MI_BIGSPY_BASE_URL", "https://api.bigspy.example.invalid", ProviderAuthKind.API_KEY_QUERY, "BIGSPY_API_KEY", query_param_name="api_key", compliance_classification="licensed_ads_spy"),
    "poweradspy": ProviderCatalogEntry("poweradspy", "ads_spy", "sync_ads_spy", "MI_POWERADSPY_BASE_URL", "https://api.poweradspy.example.invalid", ProviderAuthKind.API_KEY_QUERY, "POWERADSPY_API_KEY", query_param_name="api_key", compliance_classification="licensed_ads_spy"),
    "substack_newsletters": ProviderCatalogEntry("substack_newsletters", "newsletter_intelligence", "sync_newsletters", "MI_SUBSTACK_NEWSLETTERS_BASE_URL", "https://api.substack-newsletters.example.invalid", ProviderAuthKind.NONE, compliance_classification="public_newsletters", terms_sensitive=True),
    "beehiiv": ProviderCatalogEntry("beehiiv", "newsletter_intelligence", "sync_newsletters", "MI_BEEHIIV_BASE_URL", "https://api.beehiiv.example.invalid", ProviderAuthKind.API_KEY_HEADER, "BEEHIIV_API_KEY", header_name="X-Api-Key", compliance_classification="public_newsletters", terms_sensitive=True),
    "convertkit_public": ProviderCatalogEntry("convertkit_public", "newsletter_intelligence", "sync_newsletters", "MI_CONVERTKIT_PUBLIC_BASE_URL", "https://api.convertkit-public.example.invalid", ProviderAuthKind.API_KEY_HEADER, "CONVERTKIT_PUBLIC_API_KEY", header_name="X-Api-Key", compliance_classification="public_newsletters", terms_sensitive=True),
    "mailchimp_public": ProviderCatalogEntry("mailchimp_public", "newsletter_intelligence", "sync_newsletters", "MI_MAILCHIMP_PUBLIC_BASE_URL", "https://api.mailchimp-public.example.invalid", ProviderAuthKind.BEARER_TOKEN, "MAILCHIMP_PUBLIC_TOKEN", compliance_classification="public_newsletters", terms_sensitive=True),
}


def resolve_provider_catalog_entry(provider: str) -> ProviderCatalogEntry:
    canonical = PROVIDER_ALIASES.get(str(provider or '').strip(), str(provider or '').strip())
    entry = PROVIDER_CATALOG.get(canonical)
    if entry is None:
        raise KeyError(f'unknown market intelligence provider: {provider}')
    return entry


PROVIDER_FAMILY_MAP: dict[str, str] = {name: entry.source_family for name, entry in PROVIDER_CATALOG.items()}


def operations_for_family(source_family: str) -> tuple[str, ...]:
    family = str(source_family or "").strip()
    return FAMILY_OPERATIONS[family]


__all__ = [
    "CANON_MARKET_INTELLIGENCE_PROVIDER_CATALOG",
    "FAMILY_OPERATIONS",
    "PROVIDER_ALIASES",
    "PROVIDER_CATALOG",
    "PROVIDER_FAMILY_MAP",
    "ProviderAuthKind",
    "ProviderCatalogEntry",
    "operations_for_family",
    "resolve_provider_catalog_entry",
]
