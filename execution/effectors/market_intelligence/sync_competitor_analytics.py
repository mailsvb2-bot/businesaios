from __future__ import annotations

from dataclasses import dataclass, field

from execution.effectors.market_intelligence._base import MarketIntelEffectorBase
from interfaces.market_intelligence.similarweb import SimilarwebConnector


@dataclass
class SyncCompetitorAnalyticsEffector(MarketIntelEffectorBase):
    action_type: str = 'sync_competitor_analytics'
    external_system: str = 'market_intelligence'
    connector: object = field(default_factory=SimilarwebConnector)
    operation: str = 'sync_analytics'
    source_family: str = 'competitor_analytics'


__all__ = ['SyncCompetitorAnalyticsEffector']
