from __future__ import annotations

from dataclasses import dataclass, field

from execution.effectors.market_intelligence._base import MarketIntelEffectorBase
from interfaces.market_intelligence.beehiiv import BeehiivConnector


@dataclass
class SyncNewsletterIntelligenceEffector(MarketIntelEffectorBase):
    action_type: str = 'sync_newsletter_intelligence'
    external_system: str = 'market_intelligence'
    connector: object = field(default_factory=BeehiivConnector)
    operation: str = 'sync_newsletters'
    source_family: str = 'newsletter_intelligence'


__all__ = ['SyncNewsletterIntelligenceEffector']
