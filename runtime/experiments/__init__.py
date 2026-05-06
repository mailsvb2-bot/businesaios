from __future__ import annotations

"""Canonical runtime package alias namespace for runtime.experiments public API."""

from runtime.package_alias_namespace import build_package_alias_namespace

CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE = True

_PUBLIC_ATTRS = {
    'Experiment': ('core.experiments.contracts', 'Experiment'),
    'ExperimentResult': ('core.experiments.contracts', 'ExperimentResult'),
    'build_experiment': ('core.experiments.builders.experiment_plan_builder', 'build_experiment'),
    'explain_experiment_result': ('core.experiments.explainers.experiment_result_explainer', 'explain_experiment_result'),
}

__getattr__, __dir__, __all__ = build_package_alias_namespace(
    __name__,
    _PUBLIC_ATTRS,
    extra_exports=['CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE'],
    install_public_api=True
)
