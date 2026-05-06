from __future__ import annotations

from importlib import import_module
from typing import Any

CANON_GROWTH_SEO_OWNER_SURFACE = True
CANON_GROWTH_SEO_ALIAS_NAMESPACE = True
_OWNER_MODULE = 'growth.seo.catalog'
_OWNER_EXPORTS = [
    'ArticleGenerator', 'ContentRefreshPlanner', 'InternalLinkingPlanner', 'KeywordClustering',
    'KeywordResearch', 'LocalIntentMapper', 'LocationPageGenerator', 'MetaGenerator', 'RankTracking',
    'SearchConsoleConnectorAdapter', 'SeoPerformanceMonitor', 'SeoStrategyBuilder', 'ServicePageGenerator'
]
_ALIAS_EXPORTS = {
    'article_generator': 'ArticleGenerator',
    'content_refresh_planner': 'ContentRefreshPlanner',
    'internal_linking_planner': 'InternalLinkingPlanner',
    'keyword_clustering': 'KeywordClustering',
    'keyword_research': 'KeywordResearch',
    'local_intent_mapper': 'LocalIntentMapper',
    'location_page_generator': 'LocationPageGenerator',
    'meta_generator': 'MetaGenerator',
    'rank_tracking': 'RankTracking',
    'search_console_connector_adapter': 'SearchConsoleConnectorAdapter',
    'seo_performance_monitor': 'SeoPerformanceMonitor',
    'seo_strategy_builder': 'SeoStrategyBuilder',
    'service_page_generator': 'ServicePageGenerator',
}

def _owner() -> Any:
    return import_module(_OWNER_MODULE)

def __getattr__(name: str) -> Any:
    if name in {'CANON_GROWTH_SEO_OWNER_SURFACE', 'CANON_GROWTH_SEO_ALIAS_NAMESPACE'}:
        return globals()[name]
    if name in _OWNER_EXPORTS:
        return getattr(_owner(), name)
    raise AttributeError(name)

def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__) | set(_OWNER_EXPORTS))

__all__ = ['CANON_GROWTH_SEO_ALIAS_NAMESPACE', 'CANON_GROWTH_SEO_OWNER_SURFACE', *_OWNER_EXPORTS]
