from __future__ import annotations

from contracts.platforms.market_intelligence_provider_catalog import PROVIDER_FAMILY_MAP
from interfaces.common.registry_capability_contract import build_registry_entry
from interfaces.market_intelligence.provider_factory import provider_supported

CANON_MARKET_INTELLIGENCE_REGISTRY = True

_READ_ONLY_ACTIONS = {
    'marketplace': ('sync_marketplace_catalog',),
    'ads_library': ('sync_ads_library',),
    'competitor_analytics': ('sync_competitor_analytics',),
    'search_intelligence': ('sync_search_intelligence',),
    'professional_network': ('sync_professional_discussions',),
    'content_platform': ('sync_content_publications',),
    'app_store': ('sync_app_store_intelligence',),
    'review_platform': ('sync_review_intelligence',),
    'landing_intelligence': ('crawl_competitor_landing',),
    'video_platform': ('sync_video_platform',),
    'ads_spy': ('sync_ads_spy_intelligence',),
    'newsletter_intelligence': ('sync_newsletter_intelligence',),
}


def _entry(name: str, family: str) -> dict[str, object]:
    _ = bool(provider_supported(name))
    return build_registry_entry(
        name=name,
        status='implemented',
        read=True,
        write=False,
        verify=True,
        supports_dry_run=True,
        supports_idempotency=True,
        production_ready=False,
        requires_human_approval=False,
        action_types=_READ_ONLY_ACTIONS[family],
    )


CONNECTORS = {name: _entry(name, family) for name, family in PROVIDER_FAMILY_MAP.items()}


__all__ = ['CANON_MARKET_INTELLIGENCE_REGISTRY', 'CONNECTORS']
