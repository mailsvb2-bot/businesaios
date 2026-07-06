"""Canonical runtime package alias namespace for runtime.simulation public API."""

from __future__ import annotations

from runtime.package_alias_namespace import build_package_alias_namespace

CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE = True

_PUBLIC_ATTRS = {
    'ScenarioInput': ('core.simulation.contracts', 'ScenarioInput'),
    'ScenarioOutcome': ('core.simulation.contracts', 'ScenarioOutcome'),
    'build_named_scenario': ('core.simulation.builders.scenario_builder', 'build_named_scenario'),
    'explain_scenario_outcome': ('core.simulation.explainers.scenario_explainer', 'explain_scenario_outcome'),
}

__getattr__, __dir__, __all__ = build_package_alias_namespace(
    __name__,
    _PUBLIC_ATTRS,
    extra_exports=['CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE'],
    install_public_api=True
)
