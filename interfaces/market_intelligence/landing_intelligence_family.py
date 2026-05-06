from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.base import MarketIntelConnectorBase


@dataclass
class LandingIntelligenceFamilyConnector(MarketIntelConnectorBase):
    source_family: str = 'landing_intelligence'


__all__ = ['LandingIntelligenceFamilyConnector']
