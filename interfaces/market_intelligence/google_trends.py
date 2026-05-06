from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.search_intelligence_family import SearchIntelligenceFamilyConnector


@dataclass
class GoogleTrendsConnector(SearchIntelligenceFamilyConnector):
    connector_name: str = 'google_trends'
    connector_id: str = 'google_trends'
    provider_key: str = 'google'
    version: str = 'v1'


__all__ = ['GoogleTrendsConnector']
