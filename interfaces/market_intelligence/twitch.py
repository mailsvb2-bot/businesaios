from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.video_platform_family import VideoPlatformFamilyConnector


@dataclass
class TwitchConnector(VideoPlatformFamilyConnector):
    connector_name: str = 'twitch'
    connector_id: str = 'twitch'
    provider_key: str = 'twitch'
    version: str = 'v1'


__all__ = ['TwitchConnector']
