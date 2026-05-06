from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.base import MarketIntelConnectorBase


@dataclass
class AdsSpyFamilyConnector(MarketIntelConnectorBase):
    source_family: str = 'ads_spy'


__all__ = ['AdsSpyFamilyConnector']
