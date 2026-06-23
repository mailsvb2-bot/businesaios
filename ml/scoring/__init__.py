from __future__ import annotations

from importlib import import_module
from canon.public_api_alias import install_owner_alias_modules
from typing import Any

CANON_ML_SCORING_OWNER_SURFACE = True
_OWNER_MODULE = 'ml.scoring.catalog'
_OWNER_EXPORTS = [
    'AudienceScoreModel', 'ChannelScoreModel', 'CreativeScoreModel', 'LeadQualityModel',
    'PlatformMatchModel', 'RevenuePotentialModel', 'RiskScoreModel', 'SeoOpportunityModel'
]
_ALIAS_EXPORTS = {
    'audience_score_model': 'AudienceScoreModel',
    'channel_score_model': 'ChannelScoreModel',
    'creative_score_model': 'CreativeScoreModel',
    'lead_quality_model': 'LeadQualityModel',
    'platform_match_model': 'PlatformMatchModel',
    'revenue_potential_model': 'RevenuePotentialModel',
    'risk_score_model': 'RiskScoreModel',
    'seo_opportunity_model': 'SeoOpportunityModel',
}

def _owner() -> Any:
    return import_module(_OWNER_MODULE)

def __getattr__(name: str) -> Any:
    if name == 'CANON_ML_SCORING_OWNER_SURFACE':
        return CANON_ML_SCORING_OWNER_SURFACE
    if name in _OWNER_EXPORTS:
        return getattr(_owner(), name)
    raise AttributeError(name)


def _install_compat_aliases() -> None:
    install_owner_alias_modules(__name__, _ALIAS_EXPORTS, owner_getter=_owner)


_install_compat_aliases()

def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__) | set(_OWNER_EXPORTS))

__all__ = ['CANON_ML_SCORING_OWNER_SURFACE', *_OWNER_EXPORTS]
