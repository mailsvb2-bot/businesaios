from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.base import MarketIntelConnectorBase


@dataclass
class AppStoreFamilyConnector(MarketIntelConnectorBase):
    source_family: str = 'app_store'


__all__ = ['AppStoreFamilyConnector']
