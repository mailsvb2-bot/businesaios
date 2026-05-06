from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.content_platform_family import ContentPlatformFamilyConnector


@dataclass
class MediumConnector(ContentPlatformFamilyConnector):
    connector_name: str = 'medium'
    connector_id: str = 'medium'
    provider_key: str = 'medium'
    version: str = 'v1'


__all__ = ['MediumConnector']
