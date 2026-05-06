from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.content_platform_family import ContentPlatformFamilyConnector


@dataclass
class SubstackPublicationsConnector(ContentPlatformFamilyConnector):
    connector_name: str = 'substack_publications'
    connector_id: str = 'substack_publications'
    provider_key: str = 'substack'
    version: str = 'v1'


__all__ = ['SubstackPublicationsConnector']
