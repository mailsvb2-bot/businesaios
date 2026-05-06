from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.marketplace_family import MarketplaceFamilyConnector


@dataclass
class WoocommerceStoreConnector(MarketplaceFamilyConnector):
    connector_name: str = 'woocommerce_store'
    connector_id: str = 'woocommerce_store'
    provider_key: str = 'woocommerce'
    version: str = 'v1'


__all__ = ['WoocommerceStoreConnector']
