from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.professional_network_family import ProfessionalNetworkFamilyConnector


@dataclass
class RedditConnector(ProfessionalNetworkFamilyConnector):
    connector_name: str = 'reddit'
    connector_id: str = 'reddit'
    provider_key: str = 'reddit'
    version: str = 'v1'


__all__ = ['RedditConnector']
