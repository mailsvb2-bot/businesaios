from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.review_platform_family import ReviewPlatformFamilyConnector


@dataclass
class CapterraConnector(ReviewPlatformFamilyConnector):
    connector_name: str = 'capterra'
    connector_id: str = 'capterra'
    provider_key: str = 'capterra'
    version: str = 'v1'


__all__ = ['CapterraConnector']
