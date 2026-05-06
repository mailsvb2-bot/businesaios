from __future__ import annotations

from dataclasses import dataclass, field

from execution.effectors.market_intelligence._base import MarketIntelEffectorBase
from interfaces.market_intelligence.google_search import GoogleSearchConnector


@dataclass
class SyncSearchIntelligenceEffector(MarketIntelEffectorBase):
    action_type: str = 'sync_search_intelligence'
    external_system: str = 'market_intelligence'
    connector: object = field(default_factory=GoogleSearchConnector)
    operation: str = 'sync_search_results'
    source_family: str = 'search_intelligence'


__all__ = ['SyncSearchIntelligenceEffector']
