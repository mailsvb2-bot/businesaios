from __future__ import annotations

from dataclasses import dataclass, field

from execution.effectors.market_intelligence._base import MarketIntelEffectorBase
from interfaces.market_intelligence.adspy import AdspyConnector


@dataclass
class SyncAdsSpyIntelligenceEffector(MarketIntelEffectorBase):
    action_type: str = 'sync_ads_spy_intelligence'
    external_system: str = 'market_intelligence'
    connector: object = field(default_factory=AdspyConnector)
    operation: str = 'sync_ads_spy'
    source_family: str = 'ads_spy'


__all__ = ['SyncAdsSpyIntelligenceEffector']
