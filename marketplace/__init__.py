from __future__ import annotations

"""Canonical marketplace owner surface.

The package root owns the marketplace public surface directly, while
``marketplace.catalog`` remains the canonical implementation owner for most
marketplace helper wrappers. Historical leaf-module imports stay stable through
compat alias modules installed here.
"""

from importlib import import_module
from typing import Any

from supply_directory.business_directory import BusinessDirectory
from supply_directory.business_profile_store import BusinessProfileStore

CANON_MARKETPLACE_OWNER = True
CANON_MARKETPLACE_SUPPLY_ALIAS_NAMESPACE = True
_OWNER_MODULE = 'marketplace.catalog'
_OWNER_EXPORTS = [
    'BusinessCards', 'BusinessReputationIndex', 'ClientEntrypoints', 'ClientIntentRegistry', 'DemandPipeline',
    'LeadExchange', 'LocationPages', 'MarketplaceMetrics', 'MarketplacePolicy', 'MarketplaceRanking',
    'NetworkGrowthMetrics', 'RecommendationEngine', 'RecommendationFeed', 'RequestQuoteFlow', 'ReviewSurface',
    'SearchResultsBuilder', 'ServiceCategoryTree', 'process_demand'
]

def _owner() -> Any:
    return import_module(_OWNER_MODULE)

def __getattr__(name: str) -> Any:
    if name in {'CANON_MARKETPLACE_OWNER', 'CANON_MARKETPLACE_SUPPLY_ALIAS_NAMESPACE'}:
        return globals()[name]
    if name in _OWNER_EXPORTS:
        return getattr(_owner(), name)
    raise AttributeError(name)

def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__) | set(_OWNER_EXPORTS))

__all__ = [
    'BusinessCards', 'BusinessDirectory', 'BusinessProfileStore', 'BusinessReputationIndex',
    'CANON_MARKETPLACE_OWNER', 'CANON_MARKETPLACE_SUPPLY_ALIAS_NAMESPACE', 'ClientEntrypoints',
    'ClientIntentRegistry', 'DemandPipeline', 'LeadExchange', 'LocationPages', 'MarketplaceMetrics',
    'MarketplacePolicy', 'MarketplaceRanking', 'NetworkGrowthMetrics', 'RecommendationEngine',
    'RecommendationFeed', 'RequestQuoteFlow', 'ReviewSurface', 'SearchResultsBuilder',
    'ServiceCategoryTree', 'process_demand'
]
