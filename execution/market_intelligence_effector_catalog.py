from __future__ import annotations

from execution.market_intelligence_effector_router import MarketIntelligenceEffectorRouter


CANON_MARKET_INTELLIGENCE_EFFECTOR_CATALOG = True

MARKET_INTELLIGENCE_ACTION_TYPES = (
    'sync_marketplace_catalog',
    'sync_ads_library',
    'sync_competitor_analytics',
    'sync_search_intelligence',
    'sync_professional_discussions',
    'sync_content_publications',
    'sync_app_store_intelligence',
    'sync_review_intelligence',
    'crawl_competitor_landing',
    'sync_video_platform',
    'sync_ads_spy_intelligence',
    'sync_newsletter_intelligence',
)


def build_market_intelligence_effector(*, action_type: str):
    return MarketIntelligenceEffectorRouter().build(action_type=action_type)


__all__ = ['CANON_MARKET_INTELLIGENCE_EFFECTOR_CATALOG', 'MARKET_INTELLIGENCE_ACTION_TYPES', 'build_market_intelligence_effector']
