from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.landing_intelligence_family import LandingIntelligenceFamilyConnector


@dataclass
class PublicLandingPagesConnector(LandingIntelligenceFamilyConnector):
    connector_name: str = 'public_landing_pages'
    connector_id: str = 'public_landing_pages'
    provider_key: str = 'web'
    version: str = 'v1'


__all__ = ['PublicLandingPagesConnector']
