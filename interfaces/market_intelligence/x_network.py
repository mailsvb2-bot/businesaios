from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.professional_network_family import ProfessionalNetworkFamilyConnector


@dataclass
class XNetworkConnector(ProfessionalNetworkFamilyConnector):
    connector_name: str = 'x_network'
    connector_id: str = 'x_network'
    provider_key: str = 'x'
    version: str = 'v1'


__all__ = ['XNetworkConnector']
