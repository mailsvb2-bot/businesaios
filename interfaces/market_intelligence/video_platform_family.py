from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.base import MarketIntelConnectorBase


@dataclass
class VideoPlatformFamilyConnector(MarketIntelConnectorBase):
    source_family: str = 'video_platform'


__all__ = ['VideoPlatformFamilyConnector']
