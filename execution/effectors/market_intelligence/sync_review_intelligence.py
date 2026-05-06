from __future__ import annotations

from dataclasses import dataclass, field

from execution.effectors.market_intelligence._base import MarketIntelEffectorBase
from interfaces.market_intelligence.trustpilot import TrustpilotConnector


@dataclass
class SyncReviewIntelligenceEffector(MarketIntelEffectorBase):
    action_type: str = 'sync_review_intelligence'
    external_system: str = 'market_intelligence'
    connector: object = field(default_factory=TrustpilotConnector)
    operation: str = 'sync_reviews'
    source_family: str = 'review_platform'


__all__ = ['SyncReviewIntelligenceEffector']
