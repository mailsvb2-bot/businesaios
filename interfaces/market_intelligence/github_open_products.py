from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.content_platform_family import ContentPlatformFamilyConnector


@dataclass
class GithubOpenProductsConnector(ContentPlatformFamilyConnector):
    connector_name: str = 'github_open_products'
    connector_id: str = 'github_open_products'
    provider_key: str = 'github'
    version: str = 'v1'


__all__ = ['GithubOpenProductsConnector']
