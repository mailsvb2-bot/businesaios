from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.video_platform_family import VideoPlatformFamilyConnector


@dataclass
class DailymotionConnector(VideoPlatformFamilyConnector):
    connector_name: str = 'dailymotion'
    connector_id: str = 'dailymotion'
    provider_key: str = 'dailymotion'
    version: str = 'v1'


__all__ = ['DailymotionConnector']
