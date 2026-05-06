from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.review_platform_family import ReviewPlatformFamilyConnector


@dataclass
class G2Connector(ReviewPlatformFamilyConnector):
    connector_name: str = 'g2'
    connector_id: str = 'g2'
    provider_key: str = 'g2'
    version: str = 'v1'


__all__ = ['G2Connector']
