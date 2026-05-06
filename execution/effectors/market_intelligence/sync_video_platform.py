from __future__ import annotations

from dataclasses import dataclass, field

from execution.effectors.market_intelligence._base import MarketIntelEffectorBase
from interfaces.market_intelligence.vimeo import VimeoConnector


@dataclass
class SyncVideoPlatformEffector(MarketIntelEffectorBase):
    action_type: str = 'sync_video_platform'
    external_system: str = 'market_intelligence'
    connector: object = field(default_factory=VimeoConnector)
    operation: str = 'sync_videos'
    source_family: str = 'video_platform'


__all__ = ['SyncVideoPlatformEffector']
