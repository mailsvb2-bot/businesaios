from execution.effectors.market_intelligence.sync_marketplace_catalog import (
    SyncMarketplaceCatalogEffector as SyncMarketplaceCatalogEffector,
)
from execution.effectors.market_intelligence.sync_ads_library import (
    SyncAdsLibraryEffector as SyncAdsLibraryEffector,
)
from execution.effectors.market_intelligence.sync_competitor_analytics import (
    SyncCompetitorAnalyticsEffector as SyncCompetitorAnalyticsEffector,
)
from execution.effectors.market_intelligence.sync_search_intelligence import (
    SyncSearchIntelligenceEffector as SyncSearchIntelligenceEffector,
)
from execution.effectors.market_intelligence.sync_professional_discussions import (
    SyncProfessionalDiscussionsEffector as SyncProfessionalDiscussionsEffector,
)
from execution.effectors.market_intelligence.sync_content_publications import (
    SyncContentPublicationsEffector as SyncContentPublicationsEffector,
)
from execution.effectors.market_intelligence.sync_app_store_intelligence import (
    SyncAppStoreIntelligenceEffector as SyncAppStoreIntelligenceEffector,
)
from execution.effectors.market_intelligence.sync_review_intelligence import (
    SyncReviewIntelligenceEffector as SyncReviewIntelligenceEffector,
)
from execution.effectors.market_intelligence.crawl_competitor_landing import (
    CrawlCompetitorLandingEffector as CrawlCompetitorLandingEffector,
)
from execution.effectors.market_intelligence.sync_video_platform import (
    SyncVideoPlatformEffector as SyncVideoPlatformEffector,
)
from execution.effectors.market_intelligence.sync_ads_spy_intelligence import (
    SyncAdsSpyIntelligenceEffector as SyncAdsSpyIntelligenceEffector,
)
from execution.effectors.market_intelligence.sync_newsletter_intelligence import (
    SyncNewsletterIntelligenceEffector as SyncNewsletterIntelligenceEffector,
)

__all__ = [name for name in globals() if name.endswith('Effector')]
