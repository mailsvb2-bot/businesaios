from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.content_platform_family import ContentPlatformFamilyConnector


@dataclass
class NotionPublicDocsConnector(ContentPlatformFamilyConnector):
    connector_name: str = 'notion_public_docs'
    connector_id: str = 'notion_public_docs'
    provider_key: str = 'notion'
    version: str = 'v1'


__all__ = ['NotionPublicDocsConnector']
