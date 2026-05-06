from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.base import MarketIntelConnectorBase


@dataclass
class SearchIntelligenceFamilyConnector(MarketIntelConnectorBase):
    source_family: str = 'search_intelligence'


__all__ = ['SearchIntelligenceFamilyConnector']
