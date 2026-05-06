from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.video_platform_family import VideoPlatformFamilyConnector


@dataclass
class VimeoConnector(VideoPlatformFamilyConnector):
    connector_name: str = 'vimeo'
    connector_id: str = 'vimeo'
    provider_key: str = 'vimeo'
    version: str = 'v1'


__all__ = ['VimeoConnector']
