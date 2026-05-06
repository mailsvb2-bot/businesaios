from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.base import MarketIntelConnectorBase


@dataclass
class CompetitorAnalyticsFamilyConnector(MarketIntelConnectorBase):
    source_family: str = 'competitor_analytics'


__all__ = ['CompetitorAnalyticsFamilyConnector']
