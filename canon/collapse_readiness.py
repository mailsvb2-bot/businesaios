from __future__ import annotations

"""Compatibility surfaces that are ready for controlled collapse.

A surface is marked ready when project-internal imports have already been moved
to the canonical owner layer. Remaining imports are allowed only from tests or
external callers that still rely on historical paths.
"""

CORE_RUNTIME_COLLAPSE_READY_SURFACES = {}

CORE_RUNTIME_COLLAPSED_SURFACES = {
    "runtime.executor_contract": "runtime.execution.contracts",
    "runtime.read_only_registry": "runtime.application.contracts",
    "runtime.service_exports": "runtime.application.contracts",
    "runtime.capability_access": "runtime.application.contracts",
    "runtime.typed_access": "runtime.application.contracts",
    "runtime.domain_ports": "runtime.application.contracts",
    "runtime.platform.support.serving.runtime.action_validator": "application.decision.action_validator",
    "runtime.application.action_dispatcher": "application.decision.action_dispatcher",
    "runtime.application.application_ports": "application.decision.ports",
    "runtime.application.application_service": "application.decision.decision_service",
    "runtime.application.action_result": "application.decision.action_result",
    "runtime.application.action_errors": "application.decision.action_errors",
    "runtime.application.action_result_presenter": "application.decision.action_result_presenter",
    "runtime.application.action_validator": "application.decision.action_validator",
    "core.ai.decision_trace": "core.decision.ai_decision_trace",
    "runtime.execution.telemetry": "runtime.observability.telemetry",
    "runtime.platform.support.observability.metrics": "runtime.observability.metrics",
    "core.observability.telemetry": "runtime.observability.telemetry",
    "runtime.platform.event_store._historical_split_compat": "runtime.platform.event_store.postgres_event_store / runtime.platform.event_store.sqlite_read_queries",
    "runtime.platform.event_store._sqlite_user_state": "runtime.platform.event_store.sqlite_user_state",
    "runtime.config.settings_loader": "runtime.config",
    "runtime.config.feature_flags": "runtime.config",
    "runtime.application.registry_access": "runtime.application.contracts",
    "runtime.application.service_access": "runtime.application.contracts",
    "runtime.application.access_surface": "runtime.application.contracts",
    "attribution.attribution_engine": "attribution.catalog",
    "attribution.lead_to_revenue_resolver": "attribution.catalog",
    "attribution.offline_conversion_mapper": "attribution.catalog",
    "flow.closed_loop_growth_flow": "orchestration.closed_loop_growth_orchestrator",
    "flow.decision_to_execution_flow": "execution.decision_execution_bridge",
    "flow.execution_to_feedback_flow": "orchestration.execution_feedback_bridge",
    "flow.feedback_to_strategy_flow": "orchestration.strategy_feedback_bridge",
    "flow.opportunity_to_decision_flow": "orchestration.opportunity_decision_bridge",
    "flow.signal_to_opportunity_flow": "orchestration.signal_opportunity_bridge",
    "orchestration.execution_pipeline": "execution.execution_pipeline",
    "execution.action_result_store": "execution.run_result_store",
    "runtime.executor_infra": "runtime.execution.executor_state",
    "execution.closed_loop_orchestrator.economic_state": "execution.closed_loop_economic_state",
    "execution.business_operating_memory.store_support": "execution.business_memory_store_support",
    "boot.runtime_orchestrator": "bootstrap.compose",
    "boot.runtime_integration": "bootstrap.runtime_integration",
    "runtime.runtime_boot": "bootstrap.runtime_boot",
    "boot.runtime_public_api": "bootstrap.compose",
    "boot.app_boot": "bootstrap.app_boot",
    "boot.app_public_api": "bootstrap.app_boot_surface",
    "boot.http_public_api": "bootstrap.http_boot_surface",
    "boot.public_api": "boot / runtime.bootstrap owner surfaces",
    "boot.bootstrap": "bootstrap.compose",
    "boot.facade": "bootstrap.compose / bootstrap.app_boot_surface / bootstrap.http_boot_surface",
    "runtime.bootstrap.sovereign_bootstrap": "runtime.bootstrap.sovereign_bootstrap",
    "runtime.bootstrap.runtime_builder": "runtime.bootstrap.runtime_builder",
    "runtime.bootstrap": "runtime.bootstrap.process_bootstrap / runtime.bootstrap.sovereign_bootstrap",
    "runtime.bootstrap.runtime_composition_root": "runtime.bootstrap.runtime_composition_root",
    "runtime.boot.public_api": "runtime.boot",
    "interfaces.multichannel.bridge": "runtime.messaging.bridge",
    "interfaces.multichannel.results": "runtime.messaging.delivery_result",
    "core.finance.strategic.input.economics_snapshot_financial_input_adapter": "core.finance.strategic.adapters.economics_snapshot_adapter",
}

CANON_COLLAPSE_READINESS_MANIFEST = True

__all__ = [
    "CANON_COLLAPSE_READINESS_MANIFEST",
    "CORE_RUNTIME_COLLAPSE_READY_SURFACES",
    "CORE_RUNTIME_COLLAPSED_SURFACES",
]
