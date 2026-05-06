from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.marketplace_family import MarketplaceFamilyConnector


@dataclass
class AmazonConnector(MarketplaceFamilyConnector):
    connector_name: str = 'amazon'
    connector_id: str = 'amazon'
    provider_key: str = 'amazon'
    version: str = 'v1'


__all__ = ['AmazonConnector']
