from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.marketplace_family import MarketplaceFamilyConnector


@dataclass
class WildberriesConnector(MarketplaceFamilyConnector):
    connector_name: str = 'wildberries'
    connector_id: str = 'wildberries'
    provider_key: str = 'wildberries'
    version: str = 'v1'


__all__ = ['WildberriesConnector']
