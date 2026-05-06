from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.base import MarketIntelConnectorBase


@dataclass
class ContentPlatformFamilyConnector(MarketIntelConnectorBase):
    source_family: str = 'content_platform'


__all__ = ['ContentPlatformFamilyConnector']
