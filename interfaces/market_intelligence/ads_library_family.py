from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.base import MarketIntelConnectorBase


@dataclass
class AdsLibraryFamilyConnector(MarketIntelConnectorBase):
    source_family: str = 'ads_library'


__all__ = ['AdsLibraryFamilyConnector']
