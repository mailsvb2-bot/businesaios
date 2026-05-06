from __future__ import annotations

from importlib import import_module
from typing import Any

CANON_MATCH_SCORERS_OWNER_SURFACE = True
CANON_MATCH_SCORERS_COMPAT_SHIM = True
_OWNER_MODULE = 'matching.scorers.catalog'
_OWNER_EXPORTS = [
    'CapacityFitScore', 'ConversionProbabilityScore', 'CustomerSatisfactionProbabilityScore',
    'FairDistributionScore', 'GeoFitScore', 'IntentFitScore', 'PriceFitScore',
    'RepeatPurchaseProbabilityScore', 'ReputationFitScore', 'ResponseFitScore',
    'RevenuePotentialScore', 'RiskPenaltyScore'
]
_ALIAS_EXPORTS = {
    'capacity_fit_score': 'CapacityFitScore',
    'conversion_probability_score': 'ConversionProbabilityScore',
    'customer_satisfaction_probability_score': 'CustomerSatisfactionProbabilityScore',
    'fair_distribution_score': 'FairDistributionScore',
    'geo_fit_score': 'GeoFitScore',
    'intent_fit_score': 'IntentFitScore',
    'price_fit_score': 'PriceFitScore',
    'repeat_purchase_probability_score': 'RepeatPurchaseProbabilityScore',
    'reputation_fit_score': 'ReputationFitScore',
    'response_fit_score': 'ResponseFitScore',
    'revenue_potential_score': 'RevenuePotentialScore',
    'risk_penalty_score': 'RiskPenaltyScore',
}

def _owner() -> Any:
    return import_module(_OWNER_MODULE)

def __getattr__(name: str) -> Any:
    if name in {'CANON_MATCH_SCORERS_OWNER_SURFACE', 'CANON_MATCH_SCORERS_COMPAT_SHIM'}:
        return globals()[name]
    if name in _OWNER_EXPORTS:
        return getattr(_owner(), name)
    raise AttributeError(name)

def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__) | set(_OWNER_EXPORTS))

__all__ = ['CANON_MATCH_SCORERS_COMPAT_SHIM', 'CANON_MATCH_SCORERS_OWNER_SURFACE', *_OWNER_EXPORTS]
