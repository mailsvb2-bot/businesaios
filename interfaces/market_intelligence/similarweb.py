from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.competitor_analytics_family import CompetitorAnalyticsFamilyConnector


@dataclass
class SimilarwebConnector(CompetitorAnalyticsFamilyConnector):
    connector_name: str = 'similarweb'
    connector_id: str = 'similarweb'
    provider_key: str = 'similarweb'
    version: str = 'v1'


__all__ = ['SimilarwebConnector']
