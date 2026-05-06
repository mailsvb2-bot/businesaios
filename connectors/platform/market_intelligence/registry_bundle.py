from __future__ import annotations

from connectors.platform.connector_contract import BaseConnectorPlatformAdapter
from connectors.platform.connector_registry import ConnectorRegistryEntry
from interfaces.market_intelligence.amazon import AmazonConnector
from interfaces.market_intelligence.ebay import EbayConnector
from interfaces.market_intelligence.etsy import EtsyConnector
from interfaces.market_intelligence.aliexpress import AliexpressConnector
from interfaces.market_intelligence.wildberries import WildberriesConnector
from interfaces.market_intelligence.ozon import OzonConnector
from interfaces.market_intelligence.shopify_store import ShopifyStoreConnector
from interfaces.market_intelligence.woocommerce_store import WoocommerceStoreConnector
from interfaces.market_intelligence.facebook_ad_library import FacebookAdLibraryConnector
from interfaces.market_intelligence.tiktok_ads_library import TiktokAdsLibraryConnector
from interfaces.market_intelligence.google_ads_preview import GoogleAdsPreviewConnector
from interfaces.market_intelligence.linkedin_ads_library import LinkedinAdsLibraryConnector
from interfaces.market_intelligence.pinterest_ads_library import PinterestAdsLibraryConnector
from interfaces.market_intelligence.similarweb import SimilarwebConnector
from interfaces.market_intelligence.ahrefs import AhrefsConnector
from interfaces.market_intelligence.semrush import SemrushConnector
from interfaces.market_intelligence.ubersuggest import UbersuggestConnector
from interfaces.market_intelligence.google_search import GoogleSearchConnector
from interfaces.market_intelligence.bing_search import BingSearchConnector
from interfaces.market_intelligence.duckduckgo_search import DuckduckgoSearchConnector
from interfaces.market_intelligence.google_trends import GoogleTrendsConnector
from interfaces.market_intelligence.linkedin_network import LinkedinNetworkConnector
from interfaces.market_intelligence.x_network import XNetworkConnector
from interfaces.market_intelligence.reddit import RedditConnector
from interfaces.market_intelligence.quora import QuoraConnector
from interfaces.market_intelligence.medium import MediumConnector
from interfaces.market_intelligence.substack_publications import SubstackPublicationsConnector
from interfaces.market_intelligence.notion_public_docs import NotionPublicDocsConnector
from interfaces.market_intelligence.github_open_products import GithubOpenProductsConnector
from interfaces.market_intelligence.google_play import GooglePlayConnector
from interfaces.market_intelligence.apple_app_store import AppleAppStoreConnector
from interfaces.market_intelligence.app_store import AppStoreConnector
from interfaces.market_intelligence.trustpilot import TrustpilotConnector
from interfaces.market_intelligence.g2 import G2Connector
from interfaces.market_intelligence.capterra import CapterraConnector
from interfaces.market_intelligence.yelp import YelpConnector
from interfaces.market_intelligence.public_landing_pages import PublicLandingPagesConnector
from interfaces.market_intelligence.vimeo import VimeoConnector
from interfaces.market_intelligence.rumble import RumbleConnector
from interfaces.market_intelligence.dailymotion import DailymotionConnector
from interfaces.market_intelligence.twitch import TwitchConnector
from interfaces.market_intelligence.adspy import AdspyConnector
from interfaces.market_intelligence.bigspy import BigspyConnector
from interfaces.market_intelligence.poweradspy import PoweradspyConnector
from interfaces.market_intelligence.substack_newsletters import SubstackNewslettersConnector
from interfaces.market_intelligence.beehiiv import BeehiivConnector
from interfaces.market_intelligence.convertkit_public import ConvertkitPublicConnector
from interfaces.market_intelligence.mailchimp_public import MailchimpPublicConnector


CANON_MARKET_INTELLIGENCE_REGISTRY_BUNDLE = True


def build_market_intelligence_registry_entries() -> tuple[ConnectorRegistryEntry, ...]:
    return (

        ConnectorRegistryEntry(
            connector_id='amazon',
            provider='amazon',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='amazon',
                provider='amazon',
                version='v1',
                connector=AmazonConnector(),
            ),
            rank=20,
            tags=('marketplace', 'amazon', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='ebay',
            provider='ebay',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='ebay',
                provider='ebay',
                version='v1',
                connector=EbayConnector(),
            ),
            rank=20,
            tags=('marketplace', 'ebay', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='etsy',
            provider='etsy',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='etsy',
                provider='etsy',
                version='v1',
                connector=EtsyConnector(),
            ),
            rank=20,
            tags=('marketplace', 'etsy', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='aliexpress',
            provider='aliexpress',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='aliexpress',
                provider='aliexpress',
                version='v1',
                connector=AliexpressConnector(),
            ),
            rank=20,
            tags=('marketplace', 'aliexpress', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='wildberries',
            provider='wildberries',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='wildberries',
                provider='wildberries',
                version='v1',
                connector=WildberriesConnector(),
            ),
            rank=20,
            tags=('marketplace', 'wildberries', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='ozon',
            provider='ozon',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='ozon',
                provider='ozon',
                version='v1',
                connector=OzonConnector(),
            ),
            rank=20,
            tags=('marketplace', 'ozon', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='shopify_store',
            provider='shopify',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='shopify_store',
                provider='shopify',
                version='v1',
                connector=ShopifyStoreConnector(),
            ),
            rank=20,
            tags=('marketplace', 'shopify', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='woocommerce_store',
            provider='woocommerce',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='woocommerce_store',
                provider='woocommerce',
                version='v1',
                connector=WoocommerceStoreConnector(),
            ),
            rank=20,
            tags=('marketplace', 'woocommerce', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='facebook_ad_library',
            provider='meta',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='facebook_ad_library',
                provider='meta',
                version='v1',
                connector=FacebookAdLibraryConnector(),
            ),
            rank=20,
            tags=('ads_library', 'meta', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='tiktok_ads_library',
            provider='tiktok',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='tiktok_ads_library',
                provider='tiktok',
                version='v1',
                connector=TiktokAdsLibraryConnector(),
            ),
            rank=20,
            tags=('ads_library', 'tiktok', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='google_ads_preview',
            provider='google',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='google_ads_preview',
                provider='google',
                version='v1',
                connector=GoogleAdsPreviewConnector(),
            ),
            rank=20,
            tags=('ads_library', 'google', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='linkedin_ads_library',
            provider='linkedin',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='linkedin_ads_library',
                provider='linkedin',
                version='v1',
                connector=LinkedinAdsLibraryConnector(),
            ),
            rank=20,
            tags=('ads_library', 'linkedin', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='pinterest_ads_library',
            provider='pinterest',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='pinterest_ads_library',
                provider='pinterest',
                version='v1',
                connector=PinterestAdsLibraryConnector(),
            ),
            rank=20,
            tags=('ads_library', 'pinterest', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='similarweb',
            provider='similarweb',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='similarweb',
                provider='similarweb',
                version='v1',
                connector=SimilarwebConnector(),
            ),
            rank=30,
            tags=('competitor_analytics', 'similarweb', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='ahrefs',
            provider='ahrefs',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='ahrefs',
                provider='ahrefs',
                version='v1',
                connector=AhrefsConnector(),
            ),
            rank=30,
            tags=('competitor_analytics', 'ahrefs', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='semrush',
            provider='semrush',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='semrush',
                provider='semrush',
                version='v1',
                connector=SemrushConnector(),
            ),
            rank=30,
            tags=('competitor_analytics', 'semrush', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='ubersuggest',
            provider='ubersuggest',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='ubersuggest',
                provider='ubersuggest',
                version='v1',
                connector=UbersuggestConnector(),
            ),
            rank=30,
            tags=('competitor_analytics', 'ubersuggest', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='google_search',
            provider='google',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='google_search',
                provider='google',
                version='v1',
                connector=GoogleSearchConnector(),
            ),
            rank=20,
            tags=('search_intelligence', 'google', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='bing_search',
            provider='bing',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='bing_search',
                provider='bing',
                version='v1',
                connector=BingSearchConnector(),
            ),
            rank=20,
            tags=('search_intelligence', 'bing', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='duckduckgo_search',
            provider='duckduckgo',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='duckduckgo_search',
                provider='duckduckgo',
                version='v1',
                connector=DuckduckgoSearchConnector(),
            ),
            rank=20,
            tags=('search_intelligence', 'duckduckgo', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='google_trends',
            provider='google',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='google_trends',
                provider='google',
                version='v1',
                connector=GoogleTrendsConnector(),
            ),
            rank=20,
            tags=('search_intelligence', 'google', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='linkedin_network',
            provider='linkedin',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='linkedin_network',
                provider='linkedin',
                version='v1',
                connector=LinkedinNetworkConnector(),
            ),
            rank=30,
            tags=('professional_network', 'linkedin', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='x_network',
            provider='x',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='x_network',
                provider='x',
                version='v1',
                connector=XNetworkConnector(),
            ),
            rank=30,
            tags=('professional_network', 'x', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='reddit',
            provider='reddit',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='reddit',
                provider='reddit',
                version='v1',
                connector=RedditConnector(),
            ),
            rank=30,
            tags=('professional_network', 'reddit', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='quora',
            provider='quora',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='quora',
                provider='quora',
                version='v1',
                connector=QuoraConnector(),
            ),
            rank=30,
            tags=('professional_network', 'quora', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='medium',
            provider='medium',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='medium',
                provider='medium',
                version='v1',
                connector=MediumConnector(),
            ),
            rank=30,
            tags=('content_platform', 'medium', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='substack_publications',
            provider='substack',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='substack_publications',
                provider='substack',
                version='v1',
                connector=SubstackPublicationsConnector(),
            ),
            rank=30,
            tags=('content_platform', 'substack', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='notion_public_docs',
            provider='notion',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='notion_public_docs',
                provider='notion',
                version='v1',
                connector=NotionPublicDocsConnector(),
            ),
            rank=30,
            tags=('content_platform', 'notion', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='github_open_products',
            provider='github',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='github_open_products',
                provider='github',
                version='v1',
                connector=GithubOpenProductsConnector(),
            ),
            rank=30,
            tags=('content_platform', 'github', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='google_play',
            provider='google',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='google_play',
                provider='google',
                version='v1',
                connector=GooglePlayConnector(),
            ),
            rank=20,
            tags=('app_store', 'google', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='app_store',
            provider='apple',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='app_store',
                provider='apple',
                version='v1',
                connector=AppStoreConnector(),
            ),
            rank=20,
            tags=('app_store', 'apple', 'market_intelligence'),
        ),

        ConnectorRegistryEntry(
            connector_id='apple_app_store',
            provider='apple_app_store',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='apple_app_store',
                provider='apple_app_store',
                version='v1',
                connector=AppleAppStoreConnector(),
            ),
            rank=20,
            tags=('app_store', 'apple_app_store', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='trustpilot',
            provider='trustpilot',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='trustpilot',
                provider='trustpilot',
                version='v1',
                connector=TrustpilotConnector(),
            ),
            rank=20,
            tags=('review_platform', 'trustpilot', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='g2',
            provider='g2',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='g2',
                provider='g2',
                version='v1',
                connector=G2Connector(),
            ),
            rank=20,
            tags=('review_platform', 'g2', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='capterra',
            provider='capterra',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='capterra',
                provider='capterra',
                version='v1',
                connector=CapterraConnector(),
            ),
            rank=20,
            tags=('review_platform', 'capterra', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='yelp',
            provider='yelp',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='yelp',
                provider='yelp',
                version='v1',
                connector=YelpConnector(),
            ),
            rank=20,
            tags=('review_platform', 'yelp', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='public_landing_pages',
            provider='web',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='public_landing_pages',
                provider='web',
                version='v1',
                connector=PublicLandingPagesConnector(),
            ),
            rank=30,
            tags=('landing_intelligence', 'web', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='vimeo',
            provider='vimeo',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='vimeo',
                provider='vimeo',
                version='v1',
                connector=VimeoConnector(),
            ),
            rank=20,
            tags=('video_platform', 'vimeo', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='rumble',
            provider='rumble',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='rumble',
                provider='rumble',
                version='v1',
                connector=RumbleConnector(),
            ),
            rank=20,
            tags=('video_platform', 'rumble', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='dailymotion',
            provider='dailymotion',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='dailymotion',
                provider='dailymotion',
                version='v1',
                connector=DailymotionConnector(),
            ),
            rank=20,
            tags=('video_platform', 'dailymotion', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='twitch',
            provider='twitch',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='twitch',
                provider='twitch',
                version='v1',
                connector=TwitchConnector(),
            ),
            rank=20,
            tags=('video_platform', 'twitch', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='adspy',
            provider='adspy',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='adspy',
                provider='adspy',
                version='v1',
                connector=AdspyConnector(),
            ),
            rank=30,
            tags=('ads_spy', 'adspy', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='bigspy',
            provider='bigspy',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='bigspy',
                provider='bigspy',
                version='v1',
                connector=BigspyConnector(),
            ),
            rank=30,
            tags=('ads_spy', 'bigspy', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='poweradspy',
            provider='poweradspy',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='poweradspy',
                provider='poweradspy',
                version='v1',
                connector=PoweradspyConnector(),
            ),
            rank=30,
            tags=('ads_spy', 'poweradspy', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='substack_newsletters',
            provider='substack',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='substack_newsletters',
                provider='substack',
                version='v1',
                connector=SubstackNewslettersConnector(),
            ),
            rank=30,
            tags=('newsletter_intelligence', 'substack', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='beehiiv',
            provider='beehiiv',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='beehiiv',
                provider='beehiiv',
                version='v1',
                connector=BeehiivConnector(),
            ),
            rank=30,
            tags=('newsletter_intelligence', 'beehiiv', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='convertkit_public',
            provider='convertkit',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='convertkit_public',
                provider='convertkit',
                version='v1',
                connector=ConvertkitPublicConnector(),
            ),
            rank=30,
            tags=('newsletter_intelligence', 'convertkit', 'market_intelligence'),
        ),
        ConnectorRegistryEntry(
            connector_id='mailchimp_public',
            provider='mailchimp',
            version='v1',
            connector=BaseConnectorPlatformAdapter(
                connector_id='mailchimp_public',
                provider='mailchimp',
                version='v1',
                connector=MailchimpPublicConnector(),
            ),
            rank=30,
            tags=('newsletter_intelligence', 'mailchimp', 'market_intelligence'),
        ),
    )


__all__ = ['CANON_MARKET_INTELLIGENCE_REGISTRY_BUNDLE', 'build_market_intelligence_registry_entries']
