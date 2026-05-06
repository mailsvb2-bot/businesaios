from __future__ import annotations

import importlib
import sys
from typing import Any

CANON_GROWTH_CORE_ALIAS_NAMESPACE = True

_ALIAS_MAP = {
    "growth_cycle": "growth.core.growth_engine",
    "growth_memory": "growth.core.growth_engine",
    "growth_plan_builder": "growth.core.growth_engine",
    "growth_state_transition": "growth.core.growth_engine",
    "opportunity_detector": "growth.core.growth_engine",
    "opportunity_ranker": "growth.core.growth_engine",
    "revenue_feedback_loop": "growth.core.growth_engine",
    "state_snapshot": "growth.core.growth_engine",
    "opportunity_registry": "shared.registry",
}

_PUBLIC_ATTRS = {
    "GrowthCycle": ("growth.core.growth_engine", "GrowthCycle"),
    "GrowthEngine": ("growth.core.growth_engine", "GrowthEngine"),
    "GrowthMemory": ("growth.core.growth_engine", "GrowthMemory"),
    "GrowthPlanBuilder": ("growth.core.growth_engine", "GrowthPlanBuilder"),
    "GrowthStateTransition": ("growth.core.growth_engine", "GrowthStateTransition"),
    "OpportunityDetector": ("growth.core.growth_engine", "OpportunityDetector"),
    "OpportunityRanker": ("growth.core.growth_engine", "OpportunityRanker"),
    "OpportunityRegistry": ("shared.registry", "OpportunityRegistry"),
    "RevenueFeedbackLoop": ("growth.core.growth_engine", "RevenueFeedbackLoop"),
    "StateSnapshot": ("growth.core.growth_engine", "StateSnapshot"),
}


def _install_aliases() -> None:
    package = sys.modules[__name__]
    for alias_name, target in _ALIAS_MAP.items():
        module = importlib.import_module(target)
        sys.modules[f"{__name__}.{alias_name}"] = module
        setattr(package, alias_name, module)


_install_aliases()


def __getattr__(name: str) -> Any:
    target = _PUBLIC_ATTRS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attr_name = target
    module = importlib.import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


__all__ = ["CANON_GROWTH_CORE_ALIAS_NAMESPACE", *sorted(_PUBLIC_ATTRS)]
