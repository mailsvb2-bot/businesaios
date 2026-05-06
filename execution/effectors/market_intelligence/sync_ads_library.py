from __future__ import annotations

from dataclasses import dataclass, field

from execution.effectors.market_intelligence._base import MarketIntelEffectorBase
from interfaces.market_intelligence.facebook_ad_library import FacebookAdLibraryConnector


@dataclass
class SyncAdsLibraryEffector(MarketIntelEffectorBase):
    action_type: str = 'sync_ads_library'
    external_system: str = 'market_intelligence'
    connector: object = field(default_factory=FacebookAdLibraryConnector)
    operation: str = 'sync_ads'
    source_family: str = 'ads_library'


__all__ = ['SyncAdsLibraryEffector']
