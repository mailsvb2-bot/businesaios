from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.competitor_analytics_family import CompetitorAnalyticsFamilyConnector


@dataclass
class SemrushConnector(CompetitorAnalyticsFamilyConnector):
    connector_name: str = 'semrush'
    connector_id: str = 'semrush'
    provider_key: str = 'semrush'
    version: str = 'v1'


__all__ = ['SemrushConnector']
