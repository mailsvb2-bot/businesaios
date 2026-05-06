from __future__ import annotations

import importlib
import sys
from types import ModuleType

CANON_COMPAT_SHIM = True
CANON_RUNTIME_SERVING_RUNTIME_PACKAGE_OWNER = True


class ActionPostprocessor:
    def process(self, action):
        return action


class ActionService:
    def act(self, runtime, observation):
        return runtime.predict(observation)


class DegradedMode:
    def activate(self) -> dict[str, bool]:
        return {"degraded": True}


class FallbackRouter:
    def route(self, primary, fallback, use_fallback: bool):
        return fallback if use_fallback else primary


class FeatureFetcher:
    def fetch(self, observation) -> dict:
        return dict(observation.data)


class LatencyController:
    def exceeded(self, observed_ms: int, max_ms: int) -> bool:
        return observed_ms > max_ms


class ModelLoader:
    def load(self, uri: str):
        return {"uri": uri}


class PolicyRouter:
    def route(self, runtime):
        return runtime


class ResponseBuilder:
    def build(self, action) -> dict:
        return {"action": action}


class TimeoutManager:
    def timed_out(self, elapsed_ms: int, max_ms: int) -> bool:
        return elapsed_ms > max_ms


from .model_cache import ModelCache

_COMPAT_ALIAS_MAP = {
    "action_validator": "application.decision.action_validator",
}


def _install_compat_aliases() -> None:
    package = sys.modules[__name__]
    for alias_name, target in _COMPAT_ALIAS_MAP.items():
        target_module = importlib.import_module(target)
        alias_name_qualified = f"{__name__}.{alias_name}"
        sys.modules[alias_name_qualified] = target_module
        setattr(package, alias_name, target_module)


def _install_synthetic_alias_module(module_name: str, export_name: str, export_value: object) -> None:
    qualified_name = f"{__name__}.{module_name}"
    module = sys.modules.get(qualified_name)
    if module is None:
        module = ModuleType(qualified_name)
        sys.modules[qualified_name] = module
    module.__dict__.clear()
    module.__dict__.update(
        {
            "__name__": qualified_name,
            "__package__": __name__,
            "__file__": f"<synthetic:{qualified_name}>",
            export_name: export_value,
            "__all__": [export_name],
        }
    )
    setattr(sys.modules[__name__], module_name, module)


_install_compat_aliases()

for _module_name, _export_name in {
    "action_postprocessor": "ActionPostprocessor",
    "action_service": "ActionService",
    "degraded_mode": "DegradedMode",
    "fallback_router": "FallbackRouter",
    "feature_fetcher": "FeatureFetcher",
    "latency_controller": "LatencyController",
    "model_loader": "ModelLoader",
    "policy_router": "PolicyRouter",
    "response_builder": "ResponseBuilder",
    "timeout_manager": "TimeoutManager",
}.items():
    _install_synthetic_alias_module(_module_name, _export_name, globals()[_export_name])


__all__ = [
    "ActionPostprocessor",
    "ActionService",
    "CANON_COMPAT_SHIM",
    "CANON_RUNTIME_SERVING_RUNTIME_PACKAGE_OWNER",
    "DegradedMode",
    "FallbackRouter",
    "FeatureFetcher",
    "LatencyController",
    "ModelCache",
    "ModelLoader",
    "PolicyRouter",
    "ResponseBuilder",
    "TimeoutManager",
]
