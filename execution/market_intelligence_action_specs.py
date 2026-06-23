from __future__ import annotations

CANON_MARKET_INTELLIGENCE_ACTION_SPECS = True


def build_market_intelligence_action_specs():
    from execution.action_contracts import ActionSpec
    return {
        'sync_marketplace_catalog': ActionSpec(
            action_type='sync_marketplace_catalog',
            action_class='market_intelligence_read',
            externally_verified=True,
            idempotent=True,
            bounded_by_blast_radius=True,
            prod_ready=False,
            notes=('read-only marketplace intelligence ingestion', 'evidence-only; must not emit decisions'),
        ),
        'sync_ads_library': ActionSpec(
            action_type='sync_ads_library',
            action_class='market_intelligence_read',
            externally_verified=True,
            idempotent=True,
            bounded_by_blast_radius=True,
            prod_ready=False,
            notes=('read-only ad library ingestion', 'evidence-only; must not emit decisions'),
        ),
        'sync_competitor_analytics': ActionSpec(
            action_type='sync_competitor_analytics',
            action_class='market_intelligence_read',
            externally_verified=True,
            idempotent=True,
            bounded_by_blast_radius=True,
            prod_ready=False,
            notes=('read-only competitor analytics ingestion',),
        ),
        'sync_search_intelligence': ActionSpec(
            action_type='sync_search_intelligence',
            action_class='market_intelligence_read',
            externally_verified=True,
            idempotent=True,
            bounded_by_blast_radius=True,
            prod_ready=False,
            notes=('read-only search and trends ingestion',),
        ),
        'sync_professional_discussions': ActionSpec(
            action_type='sync_professional_discussions',
            action_class='market_intelligence_read',
            externally_verified=True,
            idempotent=True,
            bounded_by_blast_radius=True,
            prod_ready=False,
            notes=('read-only professional network ingestion',),
        ),
        'sync_content_publications': ActionSpec(
            action_type='sync_content_publications',
            action_class='market_intelligence_read',
            externally_verified=True,
            idempotent=True,
            bounded_by_blast_radius=True,
            prod_ready=False,
            notes=('read-only content platform ingestion',),
        ),
        'sync_app_store_intelligence': ActionSpec(
            action_type='sync_app_store_intelligence',
            action_class='market_intelligence_read',
            externally_verified=True,
            idempotent=True,
            bounded_by_blast_radius=True,
            prod_ready=False,
            notes=('read-only app-store intelligence ingestion',),
        ),
        'sync_review_intelligence': ActionSpec(
            action_type='sync_review_intelligence',
            action_class='market_intelligence_read',
            externally_verified=True,
            idempotent=True,
            bounded_by_blast_radius=True,
            prod_ready=False,
            notes=('read-only reviews ingestion',),
        ),
        'crawl_competitor_landing': ActionSpec(
            action_type='crawl_competitor_landing',
            action_class='market_intelligence_read',
            externally_verified=True,
            idempotent=True,
            bounded_by_blast_radius=True,
            prod_ready=False,
            notes=('read-only landing-page crawl',),
        ),
        'sync_video_platform': ActionSpec(
            action_type='sync_video_platform',
            action_class='market_intelligence_read',
            externally_verified=True,
            idempotent=True,
            bounded_by_blast_radius=True,
            prod_ready=False,
            notes=('read-only video-platform intelligence',),
        ),
        'sync_ads_spy_intelligence': ActionSpec(
            action_type='sync_ads_spy_intelligence',
            action_class='market_intelligence_read',
            externally_verified=True,
            idempotent=True,
            bounded_by_blast_radius=True,
            prod_ready=False,
            notes=('read-only e-commerce ads-spy intelligence',),
        ),
        'sync_newsletter_intelligence': ActionSpec(
            action_type='sync_newsletter_intelligence',
            action_class='market_intelligence_read',
            externally_verified=True,
            idempotent=True,
            bounded_by_blast_radius=True,
            prod_ready=False,
            notes=('read-only newsletter and offer ingestion',),
        ),
    }


__all__ = ['CANON_MARKET_INTELLIGENCE_ACTION_SPECS', 'build_market_intelligence_action_specs']
