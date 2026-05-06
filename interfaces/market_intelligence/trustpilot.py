from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.review_platform_family import ReviewPlatformFamilyConnector


@dataclass
class TrustpilotConnector(ReviewPlatformFamilyConnector):
    connector_name: str = 'trustpilot'
    connector_id: str = 'trustpilot'
    provider_key: str = 'trustpilot'
    version: str = 'v1'


__all__ = ['TrustpilotConnector']
