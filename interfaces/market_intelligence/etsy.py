from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.marketplace_family import MarketplaceFamilyConnector


@dataclass
class EtsyConnector(MarketplaceFamilyConnector):
    connector_name: str = 'etsy'
    connector_id: str = 'etsy'
    provider_key: str = 'etsy'
    version: str = 'v1'


__all__ = ['EtsyConnector']
