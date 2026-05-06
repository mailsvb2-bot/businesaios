from __future__ import annotations

from dataclasses import dataclass, field

from execution.effectors.market_intelligence._base import MarketIntelEffectorBase
from interfaces.market_intelligence.medium import MediumConnector


@dataclass
class SyncContentPublicationsEffector(MarketIntelEffectorBase):
    action_type: str = 'sync_content_publications'
    external_system: str = 'market_intelligence'
    connector: object = field(default_factory=MediumConnector)
    operation: str = 'sync_publications'
    source_family: str = 'content_platform'


__all__ = ['SyncContentPublicationsEffector']
