from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.marketplace_family import MarketplaceFamilyConnector


@dataclass
class AliexpressConnector(MarketplaceFamilyConnector):
    connector_name: str = 'aliexpress'
    connector_id: str = 'aliexpress'
    provider_key: str = 'aliexpress'
    version: str = 'v1'


__all__ = ['AliexpressConnector']
