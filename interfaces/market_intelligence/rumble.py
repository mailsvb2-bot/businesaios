from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.video_platform_family import VideoPlatformFamilyConnector


@dataclass
class RumbleConnector(VideoPlatformFamilyConnector):
    connector_name: str = 'rumble'
    connector_id: str = 'rumble'
    provider_key: str = 'rumble'
    version: str = 'v1'


__all__ = ['RumbleConnector']
