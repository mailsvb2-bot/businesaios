from __future__ import annotations

from dataclasses import dataclass

from interfaces.market_intelligence.search_intelligence_family import SearchIntelligenceFamilyConnector


@dataclass
class DuckduckgoSearchConnector(SearchIntelligenceFamilyConnector):
    connector_name: str = 'duckduckgo_search'
    connector_id: str = 'duckduckgo_search'
    provider_key: str = 'duckduckgo'
    version: str = 'v1'


__all__ = ['DuckduckgoSearchConnector']
