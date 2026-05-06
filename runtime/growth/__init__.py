from __future__ import annotations

"""Canonical runtime package alias namespace for runtime.growth public API."""

from runtime.package_alias_namespace import build_package_alias_namespace

CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE = True

_PUBLIC_ATTRS = {
    'GrowthGoalV1': ('core.growth.strategy.contracts', 'GrowthGoalV1'),
    'GrowthScoringContext': ('core.growth.contracts', 'GrowthScoringContext'),
    'GrowthService': ('core.growth.service', 'GrowthService'),
    'GrowthStrategyService': ('core.growth.strategy.service', 'GrowthStrategyService'),
}

__getattr__, __dir__, __all__ = build_package_alias_namespace(
    __name__,
    _PUBLIC_ATTRS,
    extra_exports=['CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE'],
    install_public_api=True
)
