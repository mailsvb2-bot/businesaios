"""Canonical runtime package alias namespace for runtime.experiments public API."""

from __future__ import annotations

from runtime.package_alias_namespace import build_package_alias_namespace

CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE = True

_PUBLIC_ATTRS = {
    "ACTION_CREATE_EXPERIMENT_V1": ("core.actions.names", "ACTION_CREATE_EXPERIMENT_V1"),
    "Experiment": ("core.experiments.contracts", "Experiment"),
    "ExperimentPlanBuilder": ("core.experiments.builders.experiment_plan_builder", "ExperimentPlanBuilder"),
    "MetricDirection": ("core.experiments.enums", "MetricDirection"),
    "VariantRole": ("core.experiments.enums", "VariantRole"),
    "ExperimentResult": ("core.experiments.contracts", "ExperimentResult"),
    "LiveCanaryCoordinator": (
        "runtime.experiments.live_canary",
        "LiveCanaryCoordinator",
    ),
    "LiveCanaryWatchdog": (
        "runtime.experiments.watchdog",
        "LiveCanaryWatchdog",
    ),
    "LiveCanaryOutcomeObserver": (
        "runtime.experiments.outcome_observer",
        "LiveCanaryOutcomeObserver",
    ),
    "LiveCanaryOutcomeSupervisor": (
        "runtime.experiments.outcome_observer",
        "LiveCanaryOutcomeSupervisor",
    ),
    "attach_live_canary": (
        "runtime.experiments.wiring",
        "attach_live_canary",
    ),
    "build_experiments_service": (
        "runtime.experiments.wiring",
        "build_experiments_service",
    ),
    "build_experiment": (
        "core.experiments.builders.experiment_plan_builder",
        "build_experiment",
    ),
    "detach_live_canary": (
        "runtime.experiments.wiring",
        "detach_live_canary",
    ),
    "start_live_canary_runtime": (
        "runtime.experiments.wiring",
        "start_live_canary_runtime",
    ),
    "explain_experiment_result": (
        "core.experiments.explainers.experiment_result_explainer",
        "explain_experiment_result",
    ),
    "validate_prefixed_id": (
        "core.experiments.ids",
        "validate_prefixed_id",
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
