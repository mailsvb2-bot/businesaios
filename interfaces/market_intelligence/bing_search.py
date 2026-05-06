from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.search_intelligence_family import SearchIntelligenceFamilyConnector


@dataclass
class BingSearchConnector(SearchIntelligenceFamilyConnector):
    connector_name: str = 'bing_search'
    connector_id: str = 'bing_search'
    provider_key: str = 'bing'
    version: str = 'v1'


__all__ = ['BingSearchConnector']
