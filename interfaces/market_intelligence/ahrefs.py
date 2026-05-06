from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.competitor_analytics_family import CompetitorAnalyticsFamilyConnector


@dataclass
class AhrefsConnector(CompetitorAnalyticsFamilyConnector):
    connector_name: str = 'ahrefs'
    connector_id: str = 'ahrefs'
    provider_key: str = 'ahrefs'
    version: str = 'v1'


__all__ = ['AhrefsConnector']
