from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.base import MarketIntelConnectorBase


@dataclass
class MarketplaceFamilyConnector(MarketIntelConnectorBase):
    source_family: str = 'marketplace'


__all__ = ['MarketplaceFamilyConnector']
