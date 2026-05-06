from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.marketplace_family import MarketplaceFamilyConnector


@dataclass
class OzonConnector(MarketplaceFamilyConnector):
    connector_name: str = 'ozon'
    connector_id: str = 'ozon'
    provider_key: str = 'ozon'
    version: str = 'v1'


__all__ = ['OzonConnector']
