"""Canonical runtime package alias namespace for runtime.economics public API."""

from __future__ import annotations


from runtime.package_alias_namespace import build_package_alias_namespace

CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE = True

_PUBLIC_ATTRS = {
    'BudgetEnvelope': ('core.economics.types', 'BudgetEnvelope'),
    'EconomicsScoringContext': ('core.economics.contracts', 'EconomicsScoringContext'),
    'EconomicsService': ('core.economics.service', 'EconomicsService'),
    'UnitEconomicsSnapshot': ('core.economics.contracts', 'UnitEconomicsSnapshot'),
    'build_budget_envelope': ('core.economics.service', 'build_budget_envelope'),
    'explain_unit_economics': ('core.economics.explainers.unit_economics_explainer', 'explain_unit_economics'),
    'normalize_objective': ('core.economics.objective', 'normalize_objective'),
}

__getattr__, __dir__, __all__ = build_package_alias_namespace(
    __name__,
    _PUBLIC_ATTRS,
    extra_exports=['CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE'],
    install_public_api=True
)
