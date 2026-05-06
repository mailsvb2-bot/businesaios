from __future__ import annotations

from dataclasses import dataclass, field

from execution.effectors.market_intelligence._base import MarketIntelEffectorBase
from interfaces.market_intelligence.amazon import AmazonConnector


@dataclass
class SyncMarketplaceCatalogEffector(MarketIntelEffectorBase):
    action_type: str = 'sync_marketplace_catalog'
    external_system: str = 'market_intelligence'
    connector: object = field(default_factory=AmazonConnector)
    operation: str = 'sync_catalog'
    source_family: str = 'marketplace'


__all__ = ['SyncMarketplaceCatalogEffector']
