from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable
from collections.abc import Mapping

from interfaces.market_intelligence.adspy import AdspyConnector
from interfaces.market_intelligence.ahrefs import AhrefsConnector
from interfaces.market_intelligence.aliexpress import AliexpressConnector
from interfaces.market_intelligence.amazon import AmazonConnector
from interfaces.market_intelligence.app_store import AppStoreConnector
from interfaces.market_intelligence.apple_app_store import AppleAppStoreConnector
from interfaces.market_intelligence.beehiiv import BeehiivConnector
from interfaces.market_intelligence.bigspy import BigspyConnector
from interfaces.market_intelligence.bing_search import BingSearchConnector
from interfaces.market_intelligence.capterra import CapterraConnector
from interfaces.market_intelligence.convertkit_public import ConvertkitPublicConnector
from interfaces.market_intelligence.dailymotion import DailymotionConnector
from interfaces.market_intelligence.duckduckgo_search import DuckduckgoSearchConnector
from interfaces.market_intelligence.ebay import EbayConnector
from interfaces.market_intelligence.etsy import EtsyConnector
from interfaces.market_intelligence.facebook_ad_library import FacebookAdLibraryConnector
from interfaces.market_intelligence.g2 import G2Connector
from interfaces.market_intelligence.github_open_products import GithubOpenProductsConnector
from interfaces.market_intelligence.google_ads_preview import GoogleAdsPreviewConnector
from interfaces.market_intelligence.google_play import GooglePlayConnector
from interfaces.market_intelligence.google_search import GoogleSearchConnector
from interfaces.market_intelligence.google_trends import GoogleTrendsConnector
from interfaces.market_intelligence.linkedin_ads_library import LinkedinAdsLibraryConnector
from interfaces.market_intelligence.linkedin_network import LinkedinNetworkConnector
from interfaces.market_intelligence.mailchimp_public import MailchimpPublicConnector
from interfaces.market_intelligence.medium import MediumConnector
from interfaces.market_intelligence.notion_public_docs import NotionPublicDocsConnector
from interfaces.market_intelligence.ozon import OzonConnector
from interfaces.market_intelligence.pinterest_ads_library import PinterestAdsLibraryConnector
from interfaces.market_intelligence.poweradspy import PoweradspyConnector
from interfaces.market_intelligence.public_landing_pages import PublicLandingPagesConnector
from interfaces.market_intelligence.quora import QuoraConnector
from interfaces.market_intelligence.reddit import RedditConnector
from interfaces.market_intelligence.rumble import RumbleConnector
from interfaces.market_intelligence.semrush import SemrushConnector
from interfaces.market_intelligence.shopify_store import ShopifyStoreConnector
from interfaces.market_intelligence.similarweb import SimilarwebConnector
from interfaces.market_intelligence.substack_newsletters import SubstackNewslettersConnector
from interfaces.market_intelligence.substack_publications import SubstackPublicationsConnector
from interfaces.market_intelligence.tiktok_ads_library import TiktokAdsLibraryConnector
from interfaces.market_intelligence.trustpilot import TrustpilotConnector
from interfaces.market_intelligence.twitch import TwitchConnector
from interfaces.market_intelligence.ubersuggest import UbersuggestConnector
from interfaces.market_intelligence.vimeo import VimeoConnector
from interfaces.market_intelligence.wildberries import WildberriesConnector
from interfaces.market_intelligence.woocommerce_store import WoocommerceStoreConnector
from interfaces.market_intelligence.x_network import XNetworkConnector
from interfaces.market_intelligence.yelp import YelpConnector


CANON_MARKET_INTELLIGENCE_CONNECTOR_RESOLVER = True


@dataclass(frozen=True)
class MarketIntelligenceConnectorResolver:
    factories: Mapping[str, Callable[[], object]] = field(default_factory=lambda: {
        'amazon': AmazonConnector,
        'ebay': EbayConnector,
        'etsy': EtsyConnector,
        'aliexpress': AliexpressConnector,
        'wildberries': WildberriesConnector,
        'ozon': OzonConnector,
        'shopify_store': ShopifyStoreConnector,
        'woocommerce_store': WoocommerceStoreConnector,
        'facebook_ad_library': FacebookAdLibraryConnector,
        'tiktok_ads_library': TiktokAdsLibraryConnector,
        'google_ads_preview': GoogleAdsPreviewConnector,
        'linkedin_ads_library': LinkedinAdsLibraryConnector,
        'pinterest_ads_library': PinterestAdsLibraryConnector,
        'similarweb': SimilarwebConnector,
        'ahrefs': AhrefsConnector,
        'semrush': SemrushConnector,
        'ubersuggest': UbersuggestConnector,
        'google_search': GoogleSearchConnector,
        'bing_search': BingSearchConnector,
        'duckduckgo_search': DuckduckgoSearchConnector,
        'google_trends': GoogleTrendsConnector,
        'linkedin_network': LinkedinNetworkConnector,
        'x_network': XNetworkConnector,
        'reddit': RedditConnector,
        'quora': QuoraConnector,
        'medium': MediumConnector,
        'substack_publications': SubstackPublicationsConnector,
        'notion_public_docs': NotionPublicDocsConnector,
        'github_open_products': GithubOpenProductsConnector,
        'google_play': GooglePlayConnector,
        'app_store': AppStoreConnector,
        'apple_app_store': AppleAppStoreConnector,
        'trustpilot': TrustpilotConnector,
        'g2': G2Connector,
        'capterra': CapterraConnector,
        'yelp': YelpConnector,
        'public_landing_pages': PublicLandingPagesConnector,
        'vimeo': VimeoConnector,
        'rumble': RumbleConnector,
        'dailymotion': DailymotionConnector,
        'twitch': TwitchConnector,
        'adspy': AdspyConnector,
        'bigspy': BigspyConnector,
        'poweradspy': PoweradspyConnector,
        'substack_newsletters': SubstackNewslettersConnector,
        'beehiiv': BeehiivConnector,
        'convertkit_public': ConvertkitPublicConnector,
        'mailchimp_public': MailchimpPublicConnector,
    })

    def build(self, provider: str) -> object:
        provider_key = str(provider or '').strip()
        factory = self.factories.get(provider_key)
        if factory is None:
            raise KeyError(f'unknown market_intelligence provider: {provider_key}')
        return factory()


__all__ = ['CANON_MARKET_INTELLIGENCE_CONNECTOR_RESOLVER', 'MarketIntelligenceConnectorResolver']
