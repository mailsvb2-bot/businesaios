"""Canonical economics namespace with lazy public exports."""
from __future__ import annotations
from typing import Any
import importlib
_EXPORT_MAP = {
    "EconomicBrain": "core.economics.brain",
    "EconomicReward": "core.economics.brain",
    "GrowthPolicy": "core.economics.brain",
    "LTVEstimator": "core.economics.brain",
    "PricingPolicy": "core.economics.brain",
    "EconomicsService": "core.economics.service",
    "EconomicsPolicySuite": "core.economics.policies",
}

def __getattr__(name: str) -> Any:
    if name in _EXPORT_MAP:
        module = importlib.import_module(_EXPORT_MAP[name])
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
__all__ = sorted(_EXPORT_MAP)
