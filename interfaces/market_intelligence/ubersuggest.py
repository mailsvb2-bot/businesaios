from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.competitor_analytics_family import CompetitorAnalyticsFamilyConnector


@dataclass
class UbersuggestConnector(CompetitorAnalyticsFamilyConnector):
    connector_name: str = 'ubersuggest'
    connector_id: str = 'ubersuggest'
    provider_key: str = 'ubersuggest'
    version: str = 'v1'


__all__ = ['UbersuggestConnector']
