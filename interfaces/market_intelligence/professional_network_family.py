from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.base import MarketIntelConnectorBase


@dataclass
class ProfessionalNetworkFamilyConnector(MarketIntelConnectorBase):
    source_family: str = 'professional_network'


__all__ = ['ProfessionalNetworkFamilyConnector']
