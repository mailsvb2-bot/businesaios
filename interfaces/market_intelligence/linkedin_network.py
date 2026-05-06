from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.professional_network_family import ProfessionalNetworkFamilyConnector


@dataclass
class LinkedinNetworkConnector(ProfessionalNetworkFamilyConnector):
    connector_name: str = 'linkedin_network'
    connector_id: str = 'linkedin_network'
    provider_key: str = 'linkedin'
    version: str = 'v1'


__all__ = ['LinkedinNetworkConnector']
