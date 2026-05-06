from __future__ import annotations

from dataclasses import dataclass, field

from execution.effectors.market_intelligence._base import MarketIntelEffectorBase
from interfaces.market_intelligence.reddit import RedditConnector


@dataclass
class SyncProfessionalDiscussionsEffector(MarketIntelEffectorBase):
    action_type: str = 'sync_professional_discussions'
    external_system: str = 'market_intelligence'
    connector: object = field(default_factory=RedditConnector)
    operation: str = 'sync_discussions'
    source_family: str = 'professional_network'


__all__ = ['SyncProfessionalDiscussionsEffector']
