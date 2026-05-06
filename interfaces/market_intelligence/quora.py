from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.professional_network_family import ProfessionalNetworkFamilyConnector


@dataclass
class QuoraConnector(ProfessionalNetworkFamilyConnector):
    connector_name: str = 'quora'
    connector_id: str = 'quora'
    provider_key: str = 'quora'
    version: str = 'v1'


__all__ = ['QuoraConnector']
