from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.marketplace_family import MarketplaceFamilyConnector


@dataclass
class ShopifyStoreConnector(MarketplaceFamilyConnector):
    connector_name: str = 'shopify_store'
    connector_id: str = 'shopify_store'
    provider_key: str = 'shopify'
    version: str = 'v1'


__all__ = ['ShopifyStoreConnector']
