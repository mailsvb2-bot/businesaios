"""Canonical runtime package alias namespace for runtime.experiments public API."""

from __future__ import annotations

from runtime.package_alias_namespace import build_package_alias_namespace

CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE = True

_PUBLIC_ATTRS = {
    "Experiment": ("core.experiments.contracts", "Experiment"),
    "ExperimentResult": ("core.experiments.contracts", "ExperimentResult"),
    "LiveCanaryCoordinator": (
        "runtime.experiments.live_canary",
        "LiveCanaryCoordinator",
    ),
    "LiveCanaryWatchdog": (
        "runtime.experiments.watchdog",
        "LiveCanaryWatchdog",
    ),
    "attach_live_canary": (
        "runtime.experiments.wiring",
        "attach_live_canary",
    ),
    "build_experiment": (
        "core.experiments.builders.experiment_plan_builder",
        "build_experiment",
    ),
    "detach_live_canary": (
        "runtime.experiments.wiring",
        "detach_live_canary",
    ),
    "explain_experiment_result": (
        "core.experiments.explainers.experiment_result_explainer",
        "explain_experiment_result",
    ),
    "record_live_canary_business_outcome": (
        "runtime.experiments.hooks",
        "record_live_canary_business_outcome",
    ),
    "record_live_canary_executor_result": (
        "runtime.experiments.hooks",
        "record_live_canary_executor_result",
    ),
}

__getattr__, __dir__, __all__ = build_package_alias_namespace(
    __name__,
    _PUBLIC_ATTRS,
    extra_exports=["CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE"],
    install_public_api=True,
)
