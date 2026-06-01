"""Canonical runtime-local boot surface and lightweight entrypoints.

This package is allowed to own runtime-local boot helpers, web attachment, and
operational adapters. It is *not* the global system assembly owner; final
assembly ownership lives in ``bootstrap`` / ``bootstrap.compose``. Historical
imports through ``runtime.boot.public_api`` are served by this package alias so
we do not need a separate re-export file.
"""

from __future__ import annotations

import sys
from importlib import import_module
from typing import Any

from runtime.public_api_alias import install_public_api_alias

CANON_RUNTIME_BOOT_PACKAGE_ROOT = True
CANON_RUNTIME_BOOT_RUNTIME_LOCAL_ONLY = True
CANON_RUNTIME_BOOT_NO_GLOBAL_ASSEMBLY_OWNERSHIP = True
CANON_RUNTIME_BOOT_COMPAT_ALIAS_PACKAGE = True

_EXPORT_MAP = {
    # Lightweight boot builder surface.
    "attach_finance_runtime": ("runtime.boot.finance_boot", "attach_finance_runtime"),
    "build_finance_event_registry": ("runtime.boot.finance_boot", "build_finance_event_registry"),
    "build_finance_job_orchestrator": ("runtime.boot.finance_boot", "build_finance_job_orchestrator"),
    "build_finance_job_registry": ("runtime.boot.finance_boot", "build_finance_job_registry"),
    "build_finance_job_specs": ("runtime.boot.finance_boot", "build_finance_job_specs"),
    "build_finance_runtime": ("runtime.boot.finance_boot", "build_finance_runtime"),
    "register_finance_jobs": ("runtime.boot.finance_boot", "register_finance_jobs"),
    "register_finance_runtime": ("runtime.boot.finance_boot", "register_finance_runtime"),
    "build_runtime_action_controls": ("runtime.boot.safety_control_boot", "build_runtime_action_controls"),
    "build_safety_control_runtime": ("runtime.boot.safety_control_boot", "build_safety_control_runtime"),
    # Canonical boot boundary previously hosted in public_api.py.
    "require_signing_secret_is_safe": ("core.ai.issuer", "require_signing_secret_is_safe"),
    "DecisionCore": ("core.decision_core", "DecisionCore"),
    "EconomicBrain": ("core.economics.brain", "EconomicBrain"),
    "EconomicReward": ("core.economics.brain", "EconomicReward"),
    "GrowthPolicy": ("core.economics.brain", "GrowthPolicy"),
    "LTVEstimator": ("core.economics.brain", "LTVEstimator"),
    "PricingPolicy": ("core.economics.brain", "PricingPolicy"),
    "CapitalAllocationEngine": ("core.economics.capital_engine", "CapitalAllocationEngine"),
    "UserState": ("core.economics.ltv_world_model", "UserState"),
    "build_ltv_world_model": ("core.economics.ltv_world_model", "build_ltv_world_model"),
    "pricing_world_model_from_dict": ("core.economics.world_model.serialize", "pricing_world_model_from_dict"),
    "MarketContext": ("core.economics.world_model.types", "MarketContext"),
    "PricingWorldModel": ("core.economics.world_model.world_model", "PricingWorldModel"),
    "WorldModelInput": ("core.economics.world_model.world_state", "WorldModelInput"),
    "EnvFlagProvider": ("core.flags.provider", "EnvFlagProvider"),
    "CampaignBudgetPolicy": ("core.growth.campaign_builder.budgeting", "CampaignBudgetPolicy"),
    "AutopilotCampaignBuilder": ("core.growth.campaign_builder.service", "AutopilotCampaignBuilder"),
    "TrafficToAdsSpec": ("core.growth.campaign_builder.spec_codec", "TrafficToAdsSpec"),
    "LearningSystem": ("core.learning.learning_system", "LearningSystem"),
    "PolicySelector": ("core.policies.selector", "PolicySelector"),
    "RewardEngine": ("core.reward.reward_engine", "RewardEngine"),
    "KillSwitch": ("core.safety.kill_switch", "KillSwitch"),
    "Keyring": ("core.security.keyring", "Keyring"),
    "StrategicHorizonEngine": ("core.strategic_horizon.engine", "StrategicHorizonEngine"),
    "AdsSpecBuilder": ("core.traffic.ads_spec_builder", "AdsSpecBuilder"),
    "AudienceSelector": ("core.traffic.audience_selector", "AudienceSelector"),
    "BidManager": ("core.traffic.bid_manager", "BidManager"),
    "BudgetAllocator": ("core.traffic.budget_allocator", "BudgetAllocator"),
    "CampaignFactory": ("core.traffic.campaign_factory", "CampaignFactory"),
    "CreativeGenerator": ("core.traffic.creative_generator", "CreativeGenerator"),
    "TrafficStrategyService": ("core.traffic.strategy_service", "TrafficStrategyService"),
}


_COMPAT_MODULE_ALIAS_MAP = {
    "ads_apply_provider": "bootstrap.ads_apply_provider",
    "ads_wiring": "bootstrap.ads_wiring",
    "ads_write_gateway": "bootstrap.ads_write_gateway",
    "assembly_runtime": "bootstrap.assembly_runtime",
    "boot_context": "bootstrap.boot_context",
    "boot_helpers": "bootstrap.boot_helpers",
    "boot_observability": "bootstrap.boot_observability",
    "boot_phases": "bootstrap.boot_phases",
    "canonical_decision_world_model": "bootstrap.canonical_decision_world_model",
    "canonical_decision_world_model_ltv": "bootstrap.canonical_decision_world_model_ltv",
    "canonical_decision_world_model_pricing": "bootstrap.canonical_decision_world_model_pricing",
    "canonical_decision_world_model_resolvers": "bootstrap.canonical_decision_world_model_resolvers",
    "decision_agi_world_model": "bootstrap.decision_agi_world_model",
    "decision_core_contract": "bootstrap.decision_core_contract",
    "entrypoint_context": "bootstrap.entrypoint_context",
    "failure_policy": "bootstrap.failure_policy",
    "finalize_runtime_args": "bootstrap.finalize_runtime_args",
    "governance_boot": "bootstrap.governance_boot",
    "governance_execution_boot": "bootstrap.governance_execution_boot",
    "handlers_wiring": "bootstrap.handlers_wiring",
    "health_server": "bootstrap.health_server",
    "human_governance_boot": "bootstrap.human_governance_boot",
    "knowledge_boot": "bootstrap.knowledge_boot",
    "knowledge_bundle": "bootstrap.knowledge_bundle",
    "knowledge_event_publisher": "bootstrap.knowledge_event_publisher",
    "knowledge_wiring": "bootstrap.knowledge_wiring",
    "logging_setup": "bootstrap.logging_setup",
    "mode_gate": "bootstrap.mode_gate",
    "product_boot": "bootstrap.product_boot",
    "product_system_builder": "bootstrap.product_system_builder",
    "product_system_builder_contracts": "bootstrap.product_system_builder_contracts",
    "product_system_builder_pipeline": "bootstrap.product_system_builder_pipeline",
    "registration_manifest": "bootstrap.registration_manifest",
    "route_surface": "bootstrap.route_surface",
    "safety_control_boot": "bootstrap.safety_control_boot",
    "self_check": "bootstrap.self_check",
    "system_builder": "bootstrap.system_builder",
    "system_builder_steps": "bootstrap.system_builder_steps",
    "tenant_hard_gate": "bootstrap.tenant_hard_gate",
    "tenant_self_check": "bootstrap.tenant_self_check",
    "world_model_boot": "bootstrap.world_model_boot",
    "world_model_boot_check": "bootstrap.world_model_boot_check",
    "world_model_builder": "bootstrap.world_model_builder",
    "world_model_contract": "bootstrap.world_model_contract",
    "world_model_forbidden_paths": "bootstrap.world_model_forbidden_paths",
    "world_model_self_check": "bootstrap.world_model_self_check",
    "world_snapshot_input_adapter": "bootstrap.world_snapshot_input_adapter",
    "world_snapshot_service": "bootstrap.world_snapshot_service",
}


def _install_compat_module_aliases() -> None:
    from types import ModuleType

    package = sys.modules[__name__]

    def _build_alias_module(qualified_name: str, target_module_name: str) -> ModuleType:
        module = ModuleType(qualified_name)
        module.__file__ = f"<compat-alias {qualified_name}>"
        module.__package__ = __name__

        def _load_target() -> ModuleType:
            target = import_module(target_module_name)
            sys.modules[qualified_name] = target
            setattr(package, qualified_name.rsplit(".", 1)[-1], target)
            return target

        def __getattr__(name: str):
            return getattr(_load_target(), name)

        def __dir__():
            return sorted(set(dir(_load_target())))

        module.__getattr__ = __getattr__  # type: ignore[attr-defined]
        module.__dir__ = __dir__  # type: ignore[attr-defined]
        return module

    for alias_name, target_module_name in _COMPAT_MODULE_ALIAS_MAP.items():
        qualified_name = f"{__name__}.{alias_name}"
        existing = sys.modules.get(qualified_name)
        if existing is None:
            existing = _build_alias_module(qualified_name, target_module_name)
            sys.modules[qualified_name] = existing
        setattr(package, alias_name, existing)


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _EXPORT_MAP[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_EXPORT_MAP))


__all__ = list(_EXPORT_MAP)



install_public_api_alias(__name__)
_install_compat_module_aliases()
