from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.marketplace_family import MarketplaceFamilyConnector


@dataclass
class EbayConnector(MarketplaceFamilyConnector):
    connector_name: str = 'ebay'
    connector_id: str = 'ebay'
    provider_key: str = 'ebay'
    version: str = 'v1'


__all__ = ['EbayConnector']
