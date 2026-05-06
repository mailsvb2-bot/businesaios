from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.base import MarketIntelConnectorBase


@dataclass
class NewsletterIntelligenceFamilyConnector(MarketIntelConnectorBase):
    source_family: str = 'newsletter_intelligence'


__all__ = ['NewsletterIntelligenceFamilyConnector']
