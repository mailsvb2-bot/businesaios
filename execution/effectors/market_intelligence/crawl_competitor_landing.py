from __future__ import annotations

from dataclasses import dataclass, field

from execution.effectors.market_intelligence._base import MarketIntelEffectorBase
from interfaces.market_intelligence.public_landing_pages import PublicLandingPagesConnector


@dataclass
class CrawlCompetitorLandingEffector(MarketIntelEffectorBase):
    action_type: str = 'crawl_competitor_landing'
    external_system: str = 'market_intelligence'
    connector: object = field(default_factory=PublicLandingPagesConnector)
    operation: str = 'crawl_landing_pages'
    source_family: str = 'landing_intelligence'


__all__ = ['CrawlCompetitorLandingEffector']
