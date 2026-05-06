from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.review_platform_family import ReviewPlatformFamilyConnector


@dataclass
class YelpConnector(ReviewPlatformFamilyConnector):
    connector_name: str = 'yelp'
    connector_id: str = 'yelp'
    provider_key: str = 'yelp'
    version: str = 'v1'


__all__ = ['YelpConnector']
