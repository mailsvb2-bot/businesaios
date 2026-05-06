from __future__ import annotations

from dataclasses import dataclass, field

from execution.effectors.market_intelligence._base import MarketIntelEffectorBase
from interfaces.market_intelligence.google_play import GooglePlayConnector


@dataclass
class SyncAppStoreIntelligenceEffector(MarketIntelEffectorBase):
    action_type: str = 'sync_app_store_intelligence'
    external_system: str = 'market_intelligence'
    connector: object = field(default_factory=GooglePlayConnector)
    operation: str = 'sync_apps'
    source_family: str = 'app_store'


__all__ = ['SyncAppStoreIntelligenceEffector']
