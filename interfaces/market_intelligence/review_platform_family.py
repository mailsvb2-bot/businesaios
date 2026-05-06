from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.base import MarketIntelConnectorBase


@dataclass
class ReviewPlatformFamilyConnector(MarketIntelConnectorBase):
    source_family: str = 'review_platform'


__all__ = ['ReviewPlatformFamilyConnector']
